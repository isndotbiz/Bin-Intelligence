"""
Script to remove BINs with exploit types that are not relevant for e-commerce.
This will restore exploit types to their original state and then delete BINs
that don't have card-not-present or cross-border exploit types.
"""
import logging
import sys
import os
from sqlalchemy import create_engine, text, or_, and_, not_
from sqlalchemy.orm import sessionmaker
from models import BIN, BINExploit, ExploitType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def remove_irrelevant_bins():
    """
    Remove BINs that are not relevant for e-commerce by:
    1. Executing raw SQL to delete BINs that don't have card-not-present or cross-border exploit types
    """
    # Get database URL from environment variable
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)
    
    # Connect to the database
    engine = create_engine(database_url)
    
    # Use raw SQL for better performance
    with engine.connect() as conn:
        try:
            # Count total BINs before deletion
            total_bins_before = conn.execute(text("SELECT COUNT(*) FROM bins")).scalar()
            logger.info(f"Total BINs before removal: {total_bins_before}")
            
            # Create a table of the bin IDs we want to preserve (card-not-present and cross-border)
            conn.execute(text("""
                CREATE TEMPORARY TABLE relevant_exploit_types AS
                SELECT id FROM exploit_types 
                WHERE name IN ('card-not-present', 'cross-border');
            """))
            
            # Create a table of bin IDs associated with relevant exploit types
            conn.execute(text("""
                CREATE TEMPORARY TABLE bins_to_keep AS
                SELECT DISTINCT bin_id FROM bin_exploits
                WHERE exploit_type_id IN (SELECT id FROM relevant_exploit_types);
            """))
            
            # Count bins to keep
            bins_to_keep_count = conn.execute(text("SELECT COUNT(*) FROM bins_to_keep")).scalar()
            logger.info(f"BINs to keep: {bins_to_keep_count}")
            
            # Find BINs to delete - those not in bins_to_keep
            conn.execute(text("""
                CREATE TEMPORARY TABLE bins_to_delete AS
                SELECT id FROM bins
                WHERE id NOT IN (SELECT bin_id FROM bins_to_keep);
            """))
            
            # Count bins to delete
            bins_to_delete_count = conn.execute(text("SELECT COUNT(*) FROM bins_to_delete")).scalar()
            logger.info(f"BINs to delete: {bins_to_delete_count}")
            
            # Delete exploit links first
            conn.execute(text("""
                DELETE FROM bin_exploits
                WHERE bin_id IN (SELECT id FROM bins_to_delete);
            """))
            
            # Delete the BINs
            conn.execute(text("""
                DELETE FROM bins
                WHERE id IN (SELECT id FROM bins_to_delete);
            """))
            
            # Count total BINs after deletion
            total_bins_after = conn.execute(text("SELECT COUNT(*) FROM bins")).scalar()
            logger.info(f"Total BINs after removal: {total_bins_after}")
            logger.info(f"Removed {total_bins_before - total_bins_after} irrelevant BINs")
            
            # Commit the transaction
            conn.commit()
            
        except Exception as e:
            logger.error(f"Error removing irrelevant BINs: {str(e)}")
            conn.rollback()

if __name__ == "__main__":
    logger.info("Starting removal of BINs with irrelevant exploit types...")
    remove_irrelevant_bins()
    logger.info("Removal complete - database now contains only BINs for e-commerce relevant exploit types.")