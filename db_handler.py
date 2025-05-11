"""
Database Handler Module

This module provides stable and efficient database access functions for BIN Intelligence System.
It serves as an abstraction layer for database operations to ensure connection stability
and prevent common database errors.
"""

import json
import logging
from typing import Dict, List, Any, Optional
import csv
import io

from sqlalchemy import create_engine, func, desc, and_, not_, or_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from models import BIN, ExploitType, BINExploit, ScanHistory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_session() -> Session:
    """Get a new database session with proper connection handling"""
    import os
    
    # Create engine with connection pooling and ping
    db_url = os.environ.get('DATABASE_URL')
    engine = create_engine(
        db_url,
        pool_pre_ping=True,  # Verify connections before using them
        pool_recycle=300,    # Recycle connections every 5 minutes
        connect_args={       # Ensure queries don't hang
            'connect_timeout': 10,
            'application_name': 'db_handler'
        }
    )
    
    # Create session
    Session = sessionmaker(bind=engine)
    return Session()

def get_all_bins() -> List[Dict[str, Any]]:
    """
    Get all BINs from the database with robust error handling.
    
    Returns:
        List of BIN dictionaries with all data
    """
    session = get_db_session()
    try:
        # Fetch all BINs
        bins = session.query(BIN).all()
        
        # Convert to list of dictionaries
        result = []
        for bin_obj in bins:
            bin_data = {
                'id': bin_obj.id,
                'bin': bin_obj.bin,
                'bank_name': bin_obj.bank_name,
                'bank_url': bin_obj.bank_url,
                'bank_phone': bin_obj.bank_phone,
                'bank_city': bin_obj.bank_city,
                'country': bin_obj.country,
                'state': bin_obj.state,
                'transaction_country': bin_obj.transaction_country,
                'scheme': bin_obj.scheme,
                'card_type': bin_obj.card_type,
                'card_category': bin_obj.card_category,
                'is_prepaid': bin_obj.is_prepaid,
                'is_commercial': bin_obj.is_commercial,
                'is_verified': bin_obj.is_verified,
                'verification_date': bin_obj.verification_date.isoformat() if bin_obj.verification_date else None,
                'data_source': bin_obj.data_source,
                'threeDS1Supported': bin_obj.threeDS1Supported,
                'threeDS2Supported': bin_obj.threeDS2Supported,
                'patch_status': bin_obj.patch_status,
                'verification_frequency': bin_obj.verification_frequency,
                'exploit_types': []
            }
            
            # Get exploit types
            for exploit in bin_obj.exploits:
                bin_data['exploit_types'].append({
                    'name': exploit.exploit_type.name if exploit.exploit_type else 'Unknown',
                    'description': exploit.exploit_type.description if exploit.exploit_type else '',
                    'frequency': exploit.frequency
                })
            
            result.append(bin_data)
        
        logger.info(f"Successfully retrieved {len(result)} BINs")
        return result
    except Exception as e:
        logger.error(f"Error in get_all_bins: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        # If any error occurs, return an empty list
        return []
    finally:
        # Always close the session
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
    session = get_db_session()
    try:
        # Base query
        query = session.query(BIN)
        
        # Apply filters
        if not include_patched:
            query = query.filter(BIN.patch_status == 'Exploitable')
            
        if country_filter:
            query = query.filter(BIN.country == country_filter.upper())
            
        if transaction_country_filter:
            query = query.filter(BIN.transaction_country == transaction_country_filter.upper())
        
        # Execute the query
        bins = query.all()
        
        # Calculate risk scores
        bin_risk_scores = []
        for bin_obj in bins:
            # Base risk score calculation:
            # - Patch status (2x weight): Exploitable=100, Patched=0
            # - Cross-border transaction risk (1.5x weight):
            #   * 100 if transaction country is different from issuing country 
            #   * 0 if same or missing transaction country
            # - 3DS support (1x weight): No support=100, 3DS1=50, 3DS2=0
            # - Verification status (0.5x weight): Verified=100, Unverified=50
            
            # 1. Patch status score (0-100) * 2.0
            patch_score = 100 if bin_obj.patch_status == 'Exploitable' else 0
            weighted_patch_score = patch_score * 2.0
            
            # 2. Cross-border score (0-100) * 1.5
            cross_border_score = 0
            if bin_obj.transaction_country and bin_obj.country and bin_obj.transaction_country != bin_obj.country:
                cross_border_score = 100
            weighted_cross_border_score = cross_border_score * 1.5
            
            # 3. 3DS support score (0-100) * 1.0
            threeds_score = 0
            if not bin_obj.threeDS1Supported and not bin_obj.threeDS2Supported:
                threeds_score = 100
            elif bin_obj.threeDS1Supported and not bin_obj.threeDS2Supported:
                threeds_score = 50
            weighted_threeds_score = threeds_score * 1.0
            
            # 4. Verification status score (0-100) * 0.5
            verification_score = 100 if bin_obj.is_verified else 50
            weighted_verification_score = verification_score * 0.5
            
            # Combined score (0-500)
            total_score = (
                weighted_patch_score + 
                weighted_cross_border_score + 
                weighted_threeds_score + 
                weighted_verification_score
            )
            
            # Get primary exploit type
            primary_exploit = None
            exploit_frequency = 0
            for exploit in bin_obj.exploits:
                if not primary_exploit or exploit.frequency > exploit_frequency:
                    primary_exploit = exploit.exploit_type.name if exploit.exploit_type else 'Unknown'
                    exploit_frequency = exploit.frequency
            
            # Create BIN entry with risk data
            bin_data = {
                'bin': bin_obj.bin,
                'bank_name': bin_obj.bank_name,
                'country': bin_obj.country,
                'state': bin_obj.state,
                'transaction_country': bin_obj.transaction_country,
                'scheme': bin_obj.scheme,
                'card_type': bin_obj.card_type,
                'is_prepaid': bin_obj.is_prepaid,
                'patch_status': bin_obj.patch_status,
                'threeDS1Supported': bin_obj.threeDS1Supported,
                'threeDS2Supported': bin_obj.threeDS2Supported,
                'is_verified': bin_obj.is_verified,
                'primary_exploit': primary_exploit,
                'risk_score': round(total_score, 2),
                'risk_factors': {
                    'patch_status': {
                        'score': patch_score,
                        'weight': 2.0,
                        'weighted_score': weighted_patch_score,
                        'description': f"{'Exploitable' if patch_score > 0 else 'Patched'}"
                    },
                    'cross_border': {
                        'score': cross_border_score,
                        'weight': 1.5,
                        'weighted_score': weighted_cross_border_score,
                        'description': f"{'Cross-border transaction' if cross_border_score > 0 else 'Domestic transaction'}"
                    },
                    'threeds_support': {
                        'score': threeds_score,
                        'weight': 1.0,
                        'weighted_score': weighted_threeds_score,
                        'description': f"{'No 3DS' if threeds_score == 100 else '3DS v1 only' if threeds_score == 50 else '3DS v2'}"
                    },
                    'verification': {
                        'score': verification_score,
                        'weight': 0.5,
                        'weighted_score': weighted_verification_score,
                        'description': f"{'Verified' if verification_score == 100 else 'Unverified'}"
                    }
                }
            }
            
            bin_risk_scores.append(bin_data)
        
        # Sort by risk score (descending)
        bin_risk_scores.sort(key=lambda x: x['risk_score'], reverse=True)
        
        # Limit the results
        bin_risk_scores = bin_risk_scores[:limit]
        
        logger.info(f"Successfully calculated risk scores for {len(bin_risk_scores)} BINs")
        return bin_risk_scores
    except Exception as e:
        logger.error(f"Error in get_blocklist_bins: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        # If any error occurs, return an empty list
        return []
    finally:
        # Always close the session
        session.close()

def get_blocklist_csv(
    limit: int = 100, 
    include_patched: bool = False,
    country_filter: Optional[str] = None,
    transaction_country_filter: Optional[str] = None
) -> str:
    """
    Get a ranked list of BINs to block in CSV format.
    
    Args:
        limit: Maximum number of BINs to return
        include_patched: Whether to include patched BINs
        country_filter: Filter by country code (e.g., 'US', 'GB')
        transaction_country_filter: Filter by transaction country code
        
    Returns:
        CSV string with BIN data
    """
    # Get the blocklist bins
    bins = get_blocklist_bins(
        limit=limit,
        include_patched=include_patched,
        country_filter=country_filter,
        transaction_country_filter=transaction_country_filter
    )
    
    # Prepare CSV output
    output = io.StringIO()
    
    # Define CSV columns
    columns = [
        'bin', 'bank_name', 'country', 'state', 'transaction_country', 
        'scheme', 'card_type', 'is_prepaid', 'patch_status', 
        'threeDS1Supported', 'threeDS2Supported', 'is_verified', 
        'primary_exploit', 'risk_score'
    ]
    
    # Create CSV writer
    writer = csv.DictWriter(
        output, 
        fieldnames=columns,
        extrasaction='ignore'  # Ignore extra fields
    )
    
    # Write header and rows
    writer.writeheader()
    writer.writerows(bins)
    
    return output.getvalue()