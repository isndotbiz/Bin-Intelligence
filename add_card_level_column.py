"""
Database migration script to add card_level column to the BIN table.
This allows displaying card tiers (Gold, Platinum, etc.) in the dashboard.
"""
import logging
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def add_card_level_column():
    """Add card_level column to bins table if it doesn't exist"""
    session = None
    try:
        # Get database URL from environment variable
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL environment variable not set")
            return False
            
        # Create engine and session with autocommit
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Check if card_level column exists
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'bins' 
                AND column_name = 'card_level'
            """))
            column_exists = result.fetchone() is not None
            
        if column_exists:
            logger.info("card_level column already exists in bins table")
            return True
            
        # Add the column to the table
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("""
                ALTER TABLE bins 
                ADD COLUMN card_level VARCHAR(20)
            """))
            
        logger.info("Successfully added card_level column to bins table")
        return True
        
    except Exception as e:
        logger.error(f"Error adding card_level column: {str(e)}")
        return False
    finally:
        if session:
            session.close()

if __name__ == "__main__":
    if add_card_level_column():
        logger.info("Migration completed successfully")
    else:
        logger.error("Migration failed")