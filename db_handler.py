"""
Database Handler Module

This module provides stable and efficient database access functions for BIN Intelligence System.
It serves as an abstraction layer for database operations to ensure connection stability
and prevent common database errors.
"""
import json
import logging
import os
from typing import List, Dict, Any, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session

from models import Base, BIN, ExploitType, BINExploit

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection setup with enhanced stability
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")
    
# Ensure DATABASE_URL is compatible with SQLAlchemy (PostgreSQL)
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# Create engine with connection pool settings for better stability
engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True,     # Test connections before using them
    pool_recycle=300,       # Recycle connections after 5 minutes
    pool_size=10,           # Connection pool size
    max_overflow=20         # Allow up to 20 extra connections when pool is full
)

# Create session factory
DBSession = sessionmaker(bind=engine)

def get_all_bins() -> List[Dict[str, Any]]:
    """
    Get all BINs from the database with robust error handling.
    
    Returns:
        List of BIN dictionaries with all data
    """
    # Create a fresh session for this request
    session = DBSession()
    
    try:
        # Execute a raw SQL query to get all BINs
        query = """
            SELECT * FROM bins
        """
        result = session.execute(text(query))
        rows = result.fetchall()
        
        # Process the results
        bins_data = []
        for row in rows:
            # Convert row to dictionary
            bin_dict = dict(row._mapping)
            
            # Get exploit types for this BIN
            exploit_query = """
                SELECT et.name
                FROM bin_exploits be
                JOIN exploit_types et ON be.exploit_type_id = et.id
                WHERE be.bin_id = :bin_id
            """
            exploit_result = session.execute(text(exploit_query), {'bin_id': bin_dict.get('id')})
            exploit_types = [row[0] for row in exploit_result]
            
            # Convert the database model to a more frontend-friendly format
            processed_bin = {
                'bin_code': bin_dict.get('bin_code', ''),
                'issuer': bin_dict.get('issuer') or 'Unknown',
                'brand': bin_dict.get('brand') or 'Unknown',
                'country': bin_dict.get('country') or 'Unknown',
                'card_type': bin_dict.get('card_type') or 'Unknown',
                'prepaid': bin_dict.get('prepaid') is True,
                'is_verified': bin_dict.get('is_verified') is True,
                'threeds1_supported': bin_dict.get('threeds1_supported') is True,
                'threeds2_supported': bin_dict.get('threeds2_supported') is True,
                'patch_status': bin_dict.get('patch_status') or 'Unknown',
                'exploit_types': exploit_types,
                'transaction_country': bin_dict.get('transaction_country') or None,
                'state': bin_dict.get('state') or None
            }
            
            bins_data.append(processed_bin)
            
        return bins_data
        
    except Exception as e:
        logger.error(f"Error in get_all_bins: {str(e)}")
        # Log detailed error for debugging
        import traceback
        logger.error(traceback.format_exc())
        return []
    finally:
        # Always close the session to prevent connection leaks
        session.close()
        
def get_blocklist_bins(
    limit: int = 100, 
    include_patched: bool = False,
    country_filter: Optional[str] = None,
    transaction_country_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get a ranked list of BINs to block with robust error handling.
    
    Args:
        limit: Maximum number of BINs to return
        include_patched: Whether to include patched BINs
        country_filter: Filter by country code (e.g., 'US', 'GB')
        transaction_country_filter: Filter by transaction country code
        
    Returns:
        List of BIN dictionaries with risk scores
    """
    # Create a fresh session for this request
    session = DBSession()
    
    try:
        # Start building the SQL query with parameters for injection safety
        query = """
            SELECT * FROM bins WHERE 1=1
        """
        params = {}
        
        # Add filters
        if not include_patched:
            query += " AND patch_status = :patch_status"
            params['patch_status'] = 'Exploitable'
            
        if country_filter:
            query += " AND country = :country"
            params['country'] = country_filter.upper()
            
        if transaction_country_filter:
            query += " AND transaction_country = :transaction_country"
            params['transaction_country'] = transaction_country_filter.upper()
        
        # Execute the raw SQL query
        result = session.execute(text(query), params)
        rows = result.fetchall()
        
        # Process the results
        bins_data = []
        for row in rows:
            # Convert row to dictionary
            bin_dict = dict(row._mapping)
            
            # Calculate risk score
            risk_score = 0
            
            # Factor 1: Patch status (0-50 points)
            if bin_dict.get('patch_status') == 'Exploitable':
                risk_score += 50
                
            # Factor 2: Cross-border fraud (0-30 points)
            # Get cross-border exploits
            exploit_query = """
                SELECT et.name
                FROM bin_exploits be
                JOIN exploit_types et ON be.exploit_type_id = et.id
                WHERE be.bin_id = :bin_id AND et.name = 'cross-border'
            """
            exploit_result = session.execute(text(exploit_query), {'bin_id': bin_dict.get('id')})
            cross_border_exploits = exploit_result.fetchall()
            
            transaction_country = bin_dict.get('transaction_country')
            country = bin_dict.get('country')
            
            has_cross_border = len(cross_border_exploits) > 0
            has_country_mismatch = (transaction_country and country and 
                                   transaction_country != country)
                                   
            if has_cross_border or has_country_mismatch:
                risk_score += 30
                
            # Factor 3: 3DS Support (0-15 points)
            has_3ds1 = bin_dict.get('threeds1_supported') is True
            has_3ds2 = bin_dict.get('threeds2_supported') is True
            if not has_3ds1 and not has_3ds2:
                risk_score += 15
                
            # Factor 4: Verification status (0-5 points)
            if bin_dict.get('is_verified') is True:
                risk_score += 5
                
            # Get exploit types
            exploits_query = """
                SELECT et.name
                FROM bin_exploits be
                JOIN exploit_types et ON be.exploit_type_id = et.id
                WHERE be.bin_id = :bin_id
            """
            exploits_result = session.execute(text(exploits_query), {'bin_id': bin_dict.get('id')})
            exploit_types = [row[0] for row in exploits_result]
            
            # Add processed data to response
            processed_bin = {
                'bin_code': bin_dict.get('bin_code', ''),
                'issuer': bin_dict.get('issuer') or 'Unknown',
                'brand': bin_dict.get('brand') or 'Unknown',
                'country': country or 'Unknown',
                'card_type': bin_dict.get('card_type') or 'Unknown',
                'is_verified': bin_dict.get('is_verified') is True,
                'threeds_supported': has_3ds1 or has_3ds2,
                'risk_score': risk_score,
                'patch_status': bin_dict.get('patch_status') or 'Unknown',
                'exploit_types': exploit_types,
                'transaction_country': transaction_country
            }
            
            # Add state information for US cards
            state = bin_dict.get('state')
            if country == 'US' and state:
                processed_bin['state'] = state
                
            bins_data.append(processed_bin)
            
        # Sort by risk score (highest first)
        bins_data = sorted(bins_data, key=lambda x: x['risk_score'], reverse=True)
        
        # Limit to requested number
        bins_data = bins_data[:limit]
        
        return bins_data
        
    except Exception as e:
        logger.error(f"Error in get_blocklist_bins: {str(e)}")
        # Log detailed error for debugging
        import traceback
        logger.error(traceback.format_exc())
        return []
    finally:
        # Always close the session to prevent connection leaks
        session.close()