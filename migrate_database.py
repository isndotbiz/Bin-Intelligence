"""
Database migration script to add transaction_country and state columns to the BIN table.
This allows for cross-border fraud detection by storing where a card was used,
and organizing US BINs by state.
"""

import os
import logging
from sqlalchemy import create_engine, text, MetaData, Table, Column, String, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get database URL from environment variable
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

# Create SQLAlchemy engine and session
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

def add_transaction_country_column():
    """Add transaction_country column to bins table if it doesn't exist"""
    try:
        # Check if the column already exists
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('bins')]
        
        if 'transaction_country' not in columns:
            logger.info("Adding transaction_country column to bins table...")
            # Add the column
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE bins ADD COLUMN transaction_country VARCHAR(2)"
                ))
            logger.info("Successfully added transaction_country column")
        else:
            logger.info("transaction_country column already exists, skipping")
        
        return True
    except Exception as e:
        logger.error(f"Error adding transaction_country column: {str(e)}")
        return False

def add_state_column():
    """Add state column to bins table if it doesn't exist"""
    try:
        # Check if the column already exists
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('bins')]
        
        if 'state' not in columns:
            logger.info("Adding state column to bins table...")
            # Add the column
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE bins ADD COLUMN state VARCHAR(2)"
                ))
            logger.info("Successfully added state column")
        else:
            logger.info("state column already exists, skipping")
        
        return True
    except Exception as e:
        logger.error(f"Error adding state column: {str(e)}")
        return False

def reset_failed_transactions():
    """Reset any failed transactions in the database"""
    try:
        # We need to reset any aborted transactions
        session.rollback()
        logger.info("Successfully rolled back any failed transactions")
        return True
    except Exception as e:
        logger.error(f"Error resetting transactions: {str(e)}")
        return False

if __name__ == "__main__":
    # First reset any failed transactions
    reset_failed_transactions()
    
    # Add transaction_country column
    transaction_country_result = add_transaction_country_column()
    
    # Add state column
    state_result = add_state_column()
    
    if transaction_country_result and state_result:
        logger.info("Database migration completed successfully")
    else:
        logger.error("Database migration failed")