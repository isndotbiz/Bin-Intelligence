import os
import logging
from models import BIN, BINExploit
from sqlalchemy import func, create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

# Configure database connection
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")
    
# Ensure DATABASE_URL is compatible with SQLAlchemy (PostgreSQL)
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
engine = create_engine(DATABASE_URL)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def clean_non_major_brands():
    """
    Clean up the database by removing all BINs that don't belong to
    major card networks (Visa, MasterCard, American Express, Discover)
    """
    # Allowed card brands (case-insensitive)
    allowed_brands = [
        'visa', 'mastercard', 'american express', 'amex', 'discover'
    ]
    
    # Find all BINs with brands not in our allowed list
    non_major_bins = db_session.query(BIN).filter(
        ~func.lower(BIN.brand).in_([b.lower() for b in allowed_brands])
    ).all()
    
    # Log how many BINs will be removed
    logger.info(f"Found {len(non_major_bins)} BINs that don't belong to major card networks")
    
    # Remove all associated exploits first (to avoid foreign key constraint errors)
    for bin_record in non_major_bins:
        # Delete all exploit associations
        db_session.query(BINExploit).filter(BINExploit.bin_id == bin_record.id).delete()
    
    # Commit the deletion of exploit associations
    db_session.commit()
    
    # Now delete the BIN records
    for bin_record in non_major_bins:
        logger.info(f"Removing BIN {bin_record.bin_code} with brand '{bin_record.brand}'")
        db_session.delete(bin_record)
    
    # Commit the deletion of BIN records
    db_session.commit()
    
    # Also clean up BINs that don't have a brand specified
    unknown_brand_bins = db_session.query(BIN).filter(
        (BIN.brand == None) | (BIN.brand == "")
    ).all()
    
    logger.info(f"Found {len(unknown_brand_bins)} BINs with unknown brands")
    
    # Remove all associated exploits first
    for bin_record in unknown_brand_bins:
        # Delete all exploit associations
        db_session.query(BINExploit).filter(BINExploit.bin_id == bin_record.id).delete()
    
    # Commit the deletion of exploit associations
    db_session.commit()
    
    # Now delete the BIN records
    for bin_record in unknown_brand_bins:
        logger.info(f"Removing BIN {bin_record.bin_code} with unknown brand")
        db_session.delete(bin_record)
    
    # Commit the deletion of BIN records
    db_session.commit()
    
    # Log the final counts
    total_bins = db_session.query(func.count(BIN.id)).scalar() or 0
    logger.info(f"Database cleanup complete. {total_bins} BINs remaining.")

if __name__ == "__main__":
    clean_non_major_brands()