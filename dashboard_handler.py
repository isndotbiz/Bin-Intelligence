"""
Dashboard Handler Module

This module provides stable database access for the dashboard to display
BIN data and statistics with improved error handling.
"""
import logging
import os
import json
from typing import List, Dict, Any, Optional
from collections import Counter

from sqlalchemy import create_engine, text, func
from sqlalchemy.orm import sessionmaker, scoped_session

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
        List of BIN dictionaries
    """
    session = DBSession()
    
    try:
        # Execute a parameterized query to get all BINs
        query = text("""
            SELECT * FROM bins
            ORDER BY id DESC
        """)
        result = session.execute(query)
        
        bins_data = []
        for row in result:
            bin_dict = dict(row._mapping)
            
            # Get exploit types for this BIN
            exploit_query = text("""
                SELECT et.name
                FROM bin_exploits be
                JOIN exploit_types et ON be.exploit_type_id = et.id
                WHERE be.bin_id = :bin_id
            """)
            exploit_result = session.execute(exploit_query, {'bin_id': bin_dict.get('id')})
            exploit_types = [row[0] for row in exploit_result.fetchall()]
            
            # Format the data for frontend consumption
            formatted_bin = {
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
                'transaction_country': bin_dict.get('transaction_country'),
                'state': bin_dict.get('state')
            }
            
            bins_data.append(formatted_bin)
            
        logger.info(f"Successfully retrieved {len(bins_data)} BINs from database")
        return bins_data
        
    except Exception as e:
        logger.error(f"Error in get_all_bins: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return []
    finally:
        session.close()

def get_dashboard_statistics() -> Dict[str, Any]:
    """
    Calculate statistics for the dashboard
    
    Returns:
        Dictionary with statistics
    """
    session = DBSession()
    
    try:
        # Get all BINs first
        bins_data = get_all_bins()
        
        # Initialize statistics
        stats = {
            'total_bins': len(bins_data),
            'verified_bins': 0,
            'patched_status': {'Patched': 0, 'Exploitable': 0, 'Unknown': 0},
            'brands': {},
            'countries': {},
            'top_issuers': {},
            'exploit_types': {},
            '3ds_support': {'Supported': 0, 'Not Supported': 0},
            'cross_border': {'count': 0, 'countries': {}},
            'states': {},
            'total_exploits': 0
        }
        
        # Process each BIN
        for bin_data in bins_data:
            # Count verified BINs
            if bin_data.get('is_verified'):
                stats['verified_bins'] += 1
                
            # Count by patch status
            patch_status = bin_data.get('patch_status', 'Unknown')
            stats['patched_status'][patch_status] = stats['patched_status'].get(patch_status, 0) + 1
            
            # Count by brand
            brand = bin_data.get('brand', 'Unknown')
            stats['brands'][brand] = stats['brands'].get(brand, 0) + 1
            
            # Count by country
            country = bin_data.get('country', 'Unknown')
            stats['countries'][country] = stats['countries'].get(country, 0) + 1
            
            # Count by issuer
            issuer = bin_data.get('issuer', 'Unknown')
            stats['top_issuers'][issuer] = stats['top_issuers'].get(issuer, 0) + 1
            
            # Count by exploit type
            exploit_types = bin_data.get('exploit_types', [])
            for exploit_type in exploit_types:
                stats['exploit_types'][exploit_type] = stats['exploit_types'].get(exploit_type, 0) + 1
                stats['total_exploits'] += 1
                
            # Count 3DS support
            has_3ds = bin_data.get('threeds1_supported') or bin_data.get('threeds2_supported')
            if has_3ds:
                stats['3ds_support']['Supported'] += 1
            else:
                stats['3ds_support']['Not Supported'] += 1
                
            # Count cross-border cases
            if 'cross-border' in exploit_types:
                stats['cross_border']['count'] += 1
                if bin_data.get('transaction_country'):
                    transaction_country = bin_data.get('transaction_country')
                    stats['cross_border']['countries'][transaction_country] = stats['cross_border']['countries'].get(transaction_country, 0) + 1
                    
            # Count by state (for US BINs)
            if country == 'US' and bin_data.get('state'):
                state = bin_data.get('state')
                stats['states'][state] = stats['states'].get(state, 0) + 1
        
        # Sort dictionaries by value for better display
        stats['brands'] = dict(sorted(stats['brands'].items(), key=lambda x: x[1], reverse=True))
        stats['countries'] = dict(sorted(stats['countries'].items(), key=lambda x: x[1], reverse=True))
        stats['top_issuers'] = dict(sorted(stats['top_issuers'].items(), key=lambda x: x[1], reverse=True)[:10])
        stats['exploit_types'] = dict(sorted(stats['exploit_types'].items(), key=lambda x: x[1], reverse=True))
        stats['states'] = dict(sorted(stats['states'].items(), key=lambda x: x[0]))  # Sort states alphabetically
        
        logger.info(f"Successfully calculated dashboard statistics for {stats['total_bins']} BINs")
        return stats
        
    except Exception as e:
        logger.error(f"Error in get_dashboard_statistics: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'total_bins': 0,
            'verified_bins': 0,
            'patched_status': {},
            'brands': {},
            'countries': {},
            'top_issuers': {},
            'exploit_types': {},
            '3ds_support': {},
            'cross_border': {'count': 0, 'countries': {}},
            'states': {},
            'total_exploits': 0,
            'error': str(e)
        }
    finally:
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
    session = DBSession()
    
    try:
        # Query for BINs with cross-border transactions
        query = text("""
            SELECT 
                b.country, 
                COUNT(*) as count
            FROM 
                bins b
            JOIN 
                bin_exploits be ON b.id = be.bin_id
            JOIN 
                exploit_types et ON be.exploit_type_id = et.id
            WHERE 
                b.transaction_country = :transaction_country
                AND b.country != :transaction_country
                AND et.name = 'cross-border'
            GROUP BY 
                b.country
            ORDER BY 
                count DESC
            LIMIT :limit
        """)
        
        result = session.execute(query, {
            'transaction_country': transaction_country,
            'limit': limit
        })
        
        # Process results
        cross_border_data = {
            'transaction_country': transaction_country,
            'countries': {}
        }
        
        for row in result:
            if row[0]:  # Skip null country values
                cross_border_data['countries'][row[0]] = row[1]
        
        # If no results, get all countries with cross-border fraud
        if not cross_border_data['countries']:
            query = text("""
                SELECT 
                    b.country, 
                    COUNT(*) as count
                FROM 
                    bins b
                JOIN 
                    bin_exploits be ON b.id = be.bin_id
                JOIN 
                    exploit_types et ON be.exploit_type_id = et.id
                WHERE 
                    et.name = 'cross-border'
                GROUP BY 
                    b.country
                ORDER BY 
                    count DESC
                LIMIT :limit
            """)
            
            result = session.execute(query, {'limit': limit})
            
            for row in result:
                if row[0]:  # Skip null country values
                    cross_border_data['countries'][row[0]] = row[1]
        
        logger.info(f"Successfully retrieved cross-border stats for {transaction_country}")
        return cross_border_data
        
    except Exception as e:
        logger.error(f"Error in get_cross_border_stats: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'transaction_country': transaction_country,
            'countries': {},
            'error': str(e)
        }
    finally:
        session.close()

def get_exploit_types() -> List[Dict[str, Any]]:
    """
    Get all exploit types from the database
    
    Returns:
        List of exploit type dictionaries
    """
    session = DBSession()
    
    try:
        query = text("""
            SELECT 
                et.id,
                et.name,
                et.description,
                COUNT(be.id) as frequency
            FROM 
                exploit_types et
            LEFT JOIN 
                bin_exploits be ON et.id = be.exploit_type_id
            GROUP BY 
                et.id, et.name, et.description
            ORDER BY 
                frequency DESC
        """)
        
        result = session.execute(query)
        
        exploit_types = []
        for row in result:
            exploit_types.append({
                'id': row[0],
                'name': row[1],
                'description': row[2] or f"Cards compromised via {row[1]}",
                'frequency': row[3]
            })
        
        logger.info(f"Successfully retrieved {len(exploit_types)} exploit types")
        return exploit_types
        
    except Exception as e:
        logger.error(f"Error in get_exploit_types: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return []
    finally:
        session.close()

def get_scan_history() -> List[Dict[str, Any]]:
    """
    Get scan history from the database
    
    Returns:
        List of scan history dictionaries
    """
    session = DBSession()
    
    try:
        query = text("""
            SELECT 
                id,
                scan_date,
                source,
                bins_found,
                bins_classified,
                scan_parameters
            FROM 
                scan_history
            ORDER BY 
                scan_date DESC
            LIMIT 20
        """)
        
        result = session.execute(query)
        
        scan_history = []
        for row in result:
            scan_history.append({
                'id': row[0],
                'scan_date': row[1].isoformat() if row[1] else None,
                'source': row[2],
                'bins_found': row[3],
                'bins_classified': row[4],
                'scan_parameters': row[5]
            })
        
        logger.info(f"Successfully retrieved {len(scan_history)} scan history entries")
        return scan_history
        
    except Exception as e:
        logger.error(f"Error in get_scan_history: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return []
    finally:
        session.close()