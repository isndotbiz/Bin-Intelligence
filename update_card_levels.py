"""
Script to update some sample BINs with card level information for testing
"""
import logging
import os
import random
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def update_sample_card_levels(count=100):
    """Update sample BINs with card level information"""
    try:
        # Get database URL from environment variable
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL environment variable not set")
            return False
            
        # Create engine and session
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Possible card levels
        card_levels = ["PLATINUM", "GOLD", "SIGNATURE", "WORLD", "STANDARD", "CLASSIC", 
                      "BUSINESS", "CORPORATE", "PREMIER", "INFINITE"]
        
        try:
            # Get BINs for update
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT id FROM bins LIMIT :count
                """), {"count": count})
                bin_ids = [row[0] for row in result.fetchall()]
            
            # Update each BIN with a random card level
            updated_count = 0
            for bin_id in bin_ids:
                card_level = random.choice(card_levels)
                with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                    conn.execute(text("""
                        UPDATE bins 
                        SET card_level = :card_level
                        WHERE id = :bin_id
                    """), {"card_level": card_level, "bin_id": bin_id})
                updated_count += 1
                
            logger.info(f"Successfully updated {updated_count} BINs with card level information")
            return True
            
        except Exception as e:
            logger.error(f"Error updating card levels: {str(e)}")
            return False
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        return False

if __name__ == "__main__":
    if update_sample_card_levels(count=200):
        logger.info("Card level update completed successfully")
    else:
        logger.error("Card level update failed")