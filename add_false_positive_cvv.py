"""
Script to add the 'false-positive-cvv' exploit type to the database.
This represents BINs with weak CVV verification that accept any CVV value.
"""
import logging
import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models import ExploitType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def add_false_positive_cvv_exploit():
    """Add the false-positive-cvv exploit type to the database if it doesn't exist"""
    # Get database URL from environment variable
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)
    
    # Connect to the database
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Check if the exploit type already exists
        exploit_type = session.query(ExploitType).filter_by(name="false-positive-cvv").first()
        
        if exploit_type:
            logger.info("'false-positive-cvv' exploit type already exists in the database")
            return
        
        # Add the new exploit type
        new_exploit_type = ExploitType(
            name="false-positive-cvv",
            description="Cards that accept any CVV input regardless of the actual CVV value"
        )
        
        session.add(new_exploit_type)
        session.commit()
        
        logger.info("Successfully added 'false-positive-cvv' exploit type to the database")
        
    except Exception as e:
        logger.error(f"Error adding false-positive-cvv exploit type: {str(e)}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    logger.info("Adding 'false-positive-cvv' exploit type to the database...")
    add_false_positive_cvv_exploit()