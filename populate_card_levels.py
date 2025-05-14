"""
Script to populate card_level column in the BIN table with sample values for testing.
"""
import logging
import os
import random
from datetime import datetime

# Configure SQLAlchemy imports
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def populate_card_levels(limit=200):
    """Populate the card_level column with sample values"""
    # Create a database engine and session
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        return False
        
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get BIN IDs from database (limited to prevent timeout)
        bin_ids = []
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT id FROM bins LIMIT {limit}"))
            bin_ids = [row[0] for row in result]
            
        if not bin_ids:
            logger.warning("No BINs found in database")
            return False
            
        # Define card levels to use
        card_levels = [
            "STANDARD", "GOLD", "PLATINUM", "SIGNATURE", 
            "WORLD", "INFINITE", "BUSINESS", "CORPORATE"
        ]
        
        # Update each BIN with a random card level
        updates = 0
        for bin_id in bin_ids:
            card_level = random.choice(card_levels)
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                conn.execute(
                    text("UPDATE bins SET card_level = :level WHERE id = :id"),
                    {"level": card_level, "id": bin_id}
                )
            updates += 1
            
            # Log progress every 100 updates
            if updates % 100 == 0:
                logger.info(f"Updated {updates} BINs with card level data")
                
        logger.info(f"Successfully populated card_level for {updates} BINs")
        return True
        
    except Exception as e:
        logger.error(f"Error populating card levels: {str(e)}")
        return False
    finally:
        session.close()

if __name__ == "__main__":
    logger.info("Starting card level population")
    start_time = datetime.now()
    
    success = populate_card_levels(limit=200)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    if success:
        logger.info(f"Card level population completed successfully in {duration} seconds")
    else:
        logger.error(f"Card level population failed after {duration} seconds")