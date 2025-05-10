import os
import logging
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, scoped_session
from models import Base, BIN, BINExploit, ExploitType, ScanHistory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configure database connection
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")
    
# Ensure DATABASE_URL is compatible with SQLAlchemy (PostgreSQL)
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
engine = create_engine(DATABASE_URL)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

def scrub_all_bins():
    """
    Complete scrub of all BINs in the database.
    This will delete all BIN records, exploits, and scan history but keep the exploit types.
    """
    # Count all BINs before removal
    bin_count = db_session.query(func.count(BIN.id)).scalar() or 0
    logger.info(f"Found {bin_count} BINs to remove from database")
    
    # Delete all BIN exploits first (to avoid foreign key constraint errors)
    db_session.query(BINExploit).delete()
    db_session.commit()
    logger.info(f"Deleted all BIN exploit associations")
    
    # Delete all BIN records
    db_session.query(BIN).delete()
    db_session.commit()
    logger.info(f"Deleted all BIN records")
    
    # Delete all scan history
    db_session.query(ScanHistory).delete()
    db_session.commit()
    logger.info(f"Deleted all scan history records")
    
    # Verify all BINs have been removed
    bin_count_after = db_session.query(func.count(BIN.id)).scalar() or 0
    logger.info(f"Database cleanup complete. {bin_count_after} BINs remaining (should be 0)")

if __name__ == "__main__":
    scrub_all_bins()