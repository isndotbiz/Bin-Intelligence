"""
Dashboard Handler Module

This module provides stable database access for the dashboard to display
BIN data and statistics with improved error handling.
"""

import json
import logging
from typing import Dict, List, Any, Optional

from sqlalchemy import create_engine, func, desc, text, and_, not_, or_
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
            'application_name': 'dashboard_handler'
        }
    )
    
    # Create session
    Session = sessionmaker(bind=engine)
    return Session()

def get_all_bins() -> List[Dict[str, Any]]:
    """
    Get all BINs from the database with robust error handling.
    
    Returns:
        List of BIN dictionaries
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
        # If any error occurs, return an empty list
        return []
    finally:
        # Always close the session
        session.close()

def get_dashboard_statistics() -> Dict[str, Any]:
    """
    Calculate statistics for the dashboard
    
    Returns:
        Dictionary with statistics
    """
    session = get_db_session()
    try:
        # Count total BINs
        total_bins = session.query(func.count(BIN.id)).scalar() or 0
        
        # Count verified BINs
        verified_bins = session.query(func.count(BIN.id)).filter(BIN.is_verified == True).scalar() or 0
        
        # Count BINs by patch status
        exploitable_bins = session.query(func.count(BIN.id)).filter(BIN.patch_status == 'Exploitable').scalar() or 0
        patched_bins = session.query(func.count(BIN.id)).filter(BIN.patch_status == 'Patched').scalar() or 0
        
        # Count BINs by scheme (card network)
        bins_by_scheme = {}
        scheme_counts = session.query(BIN.scheme, func.count(BIN.id))\
            .group_by(BIN.scheme)\
            .order_by(desc(func.count(BIN.id)))\
            .all()
        
        for scheme, count in scheme_counts:
            if scheme:
                bins_by_scheme[scheme] = count
        
        # Count BINs by country
        bins_by_country = {}
        country_counts = session.query(BIN.country, func.count(BIN.id))\
            .group_by(BIN.country)\
            .order_by(desc(func.count(BIN.id)))\
            .all()
        
        for country, count in country_counts:
            if country:
                bins_by_country[country] = count
        
        # Count BINs by transaction country
        bins_by_transaction_country = {}
        transaction_country_counts = session.query(BIN.transaction_country, func.count(BIN.id))\
            .filter(BIN.transaction_country != None)\
            .group_by(BIN.transaction_country)\
            .order_by(desc(func.count(BIN.id)))\
            .all()
        
        for country, count in transaction_country_counts:
            if country:
                bins_by_transaction_country[country] = count
                
        # Count US BINs by state
        bins_by_state = {}
        state_counts = session.query(BIN.state, func.count(BIN.id))\
            .filter(BIN.country == 'US')\
            .filter(BIN.state != None)\
            .group_by(BIN.state)\
            .order_by(BIN.state)\
            .all()
        
        for state, count in state_counts:
            if state:
                bins_by_state[state] = count
        
        # Count BINs by 3DS support
        threeDS1_supported = session.query(func.count(BIN.id)).filter(BIN.threeDS1Supported == True).scalar() or 0
        threeDS2_supported = session.query(func.count(BIN.id)).filter(BIN.threeDS2Supported == True).scalar() or 0
        
        # Compile statistics
        statistics = {
            'total_bins': total_bins,
            'verified_bins': verified_bins,
            'verification_percentage': round(verified_bins / total_bins * 100, 2) if total_bins > 0 else 0,
            'exploitable_bins': exploitable_bins,
            'patched_bins': patched_bins,
            'exploitable_percentage': round(exploitable_bins / total_bins * 100, 2) if total_bins > 0 else 0,
            'bins_by_scheme': bins_by_scheme,
            'bins_by_country': bins_by_country,
            'bins_by_transaction_country': bins_by_transaction_country,
            'bins_by_state': bins_by_state,
            'threeDS1_supported': threeDS1_supported,
            'threeDS2_supported': threeDS2_supported,
            'threeDS1_percentage': round(threeDS1_supported / total_bins * 100, 2) if total_bins > 0 else 0,
            'threeDS2_percentage': round(threeDS2_supported / total_bins * 100, 2) if total_bins > 0 else 0,
        }
        
        logger.info("Successfully calculated dashboard statistics")
        return statistics
    except Exception as e:
        logger.error(f"Error in get_dashboard_statistics: {str(e)}")
        # If any error occurs, return default statistics
        return {
            'total_bins': 0,
            'verified_bins': 0,
            'verification_percentage': 0,
            'exploitable_bins': 0,
            'patched_bins': 0,
            'exploitable_percentage': 0,
            'bins_by_scheme': {},
            'bins_by_country': {},
            'bins_by_transaction_country': {},
            'bins_by_state': {},
            'threeDS1_supported': 0,
            'threeDS2_supported': 0,
            'threeDS1_percentage': 0,
            'threeDS2_percentage': 0,
        }
    finally:
        # Always close the session
        session.close()

def get_cross_border_stats(transaction_country: str = 'US', limit: int = 5) -> Dict[str, Any]:
    """
    Get cross-border fraud statistics
    
    Args:
        transaction_country: Country where cards are being used
        limit: Number of countries to return
        
    Returns:
        Dictionary with cross-border statistics
    """
    session = get_db_session()
    try:
        # Define filters
        transaction_filter = BIN.transaction_country == transaction_country
        different_country_filter = BIN.country != transaction_country
        not_null_filter = and_(BIN.country != None, BIN.transaction_country != None)
        
        # Query for all cross-border BINs
        query = session.query(BIN)
        
        # Apply filters
        query = query.filter(transaction_filter)
        query = query.filter(different_country_filter)
        query = query.filter(not_null_filter)
        
        # Execute the query
        cross_border_bins = query.all()
            
        # Count BINs by country of origin
        country_counts = {}
        for bin_obj in cross_border_bins:
            if bin_obj.country not in country_counts:
                country_counts[bin_obj.country] = 0
            country_counts[bin_obj.country] += 1
        
        # Sort countries by count (descending)
        sorted_countries = sorted(country_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Get the top N countries
        top_countries = sorted_countries[:limit]
        
        # Prepare result
        result = {
            'transaction_country': transaction_country,
            'total_cross_border_bins': len(cross_border_bins),
            'top_countries': [
                {'country': country, 'count': count, 'percentage': round(count / len(cross_border_bins) * 100, 2) if len(cross_border_bins) > 0 else 0}
                for country, count in top_countries
            ]
        }
        
        logger.info(f"Successfully retrieved cross-border stats for {transaction_country}")
        return result
    except Exception as e:
        logger.error(f"Error in get_cross_border_stats: {str(e)}")
        # If any error occurs, return default stats
        return {
            'transaction_country': transaction_country,
            'total_cross_border_bins': 0,
            'top_countries': []
        }
    finally:
        # Always close the session
        session.close()

def get_exploit_types() -> List[Dict[str, Any]]:
    """
    Get all exploit types from the database
    
    Returns:
        List of exploit type dictionaries
    """
    session = get_db_session()
    try:
        # Get all exploit types
        exploit_types = session.query(ExploitType).all()
        
        # Convert to list of dictionaries
        exploit_data = []
        for et in exploit_types:
            exploit_data.append({
                'id': et.id,
                'name': et.name,
                'description': et.description
            })
        
        logger.info(f"Successfully retrieved {len(exploit_data)} exploit types")
        return exploit_data
    except Exception as e:
        logger.error(f"Error in get_exploit_types: {str(e)}")
        # If any error occurs, return an empty list
        return []
    finally:
        # Always close the session
        session.close()

def get_scan_history() -> List[Dict[str, Any]]:
    """
    Get scan history from the database
    
    Returns:
        List of scan history dictionaries
    """
    session = get_db_session()
    try:
        # Get scan history records
        scan_records = session.query(ScanHistory).order_by(ScanHistory.scan_date.desc()).limit(10).all()
        
        # Convert to list of dictionaries
        history_data = []
        for record in scan_records:
            try:
                # Parse scan parameters if available
                if record.scan_parameters:
                    scan_params = json.loads(record.scan_parameters)
                else:
                    scan_params = {}
            except:
                scan_params = {}
                
            history_data.append({
                'id': record.id,
                'scan_date': record.scan_date.isoformat() if record.scan_date else None,
                'source': record.source,
                'bins_found': record.bins_found,
                'bins_classified': record.bins_classified,
                'parameters': scan_params
            })
        
        logger.info(f"Successfully retrieved {len(history_data)} scan history records")
        return history_data
    except Exception as e:
        logger.error(f"Error in get_scan_history: {str(e)}")
        # If any error occurs, return an empty list
        return []
    finally:
        # Always close the session
        session.close()