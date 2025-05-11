"""
BIN Generator Module

This module provides stable and efficient functionality to generate and verify BINs
using the Neutrino API, with improved error handling and database stability.
"""
import logging
import random
import time
import os
from typing import List, Dict, Any, Tuple, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session

from bin_enricher import BinEnricher
from models import BIN, ExploitType, BINExploit, ScanHistory

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


def generate_bins(count: int = 10, include_cross_border: bool = True) -> Dict[str, Any]:
    """
    Generate and verify additional BINs using Neutrino API with improved error handling.
    
    Args:
        count: Number of BINs to generate (max 20)
        include_cross_border: Whether to include cross-border fraud detection
        
    Returns:
        Dictionary with status and results
    """
    # Create a fresh session for this request
    session = DBSession()
    
    try:
        # Process no more than 20 BINs at a time to avoid timeouts
        count = min(int(count), 20)
        
        logger.info(f"Generating {count} BINs with improved error handling")
        if include_cross_border:
            logger.info("Including cross-border fraud detection")
        
        # Get all existing BINs to avoid duplicates - use parameterized query
        query = text("SELECT bin_code FROM bins")
        result = session.execute(query)
        existing_bins = set(row[0] for row in result.fetchall())
        
        # Known vulnerable BIN prefixes by issuer (based on historical exploits)
        known_vulnerable_prefixes = [
            # Visa (4-series)
            "404", "411", "422", "424", "427", "431", "438", "440", "446", "448", 
            "449", "451", "453", "459", "462", "465", "474", "475", "476", "485",
            
            # Mastercard (5-series)
            "510", "512", "517", "518", "523", "528", "530", "539", "542", "547",
            "549", "555", "559",
            
            # American Express (3-series)
            "340", "346", "373", "374",
            
            # Discover (6-series)
            "601", "644", "649", "650", "651", "654", "659", "690"
        ]
        
        logger.info(f"Generating {count} new verified BINs (focusing on potentially exploitable BINs)")
        
        # Generate BIN combinations to try
        bins_to_verify = []
        
        # Generate more than needed to account for verification failures
        for _ in range(count * 2):  
            # 80% of the time use known vulnerable prefixes, 20% random generation
            if random.random() < 0.8 and known_vulnerable_prefixes:
                # Use known vulnerable prefixes
                prefix = random.choice(known_vulnerable_prefixes)
                
                # Complete the 6-digit BIN
                remaining_digits = 6 - len(prefix)
                bin_code = prefix + ''.join([str(random.randint(0, 9)) for _ in range(remaining_digits)])
            else:
                # Generate completely random BIN from major card networks
                first_digit = random.choice(['3', '4', '5', '6'])
                if first_digit == '3':
                    # For Amex, use only 34 or 37 as prefix
                    second_digit = random.choice(['4', '7'])
                    bin_code = '3' + second_digit + ''.join([str(random.randint(0, 9)) for _ in range(4)])
                elif first_digit == '5':
                    # For Mastercard, make sure second digit is 1-5
                    second_digit = str(random.randint(1, 5))
                    bin_code = '5' + second_digit + ''.join([str(random.randint(0, 9)) for _ in range(4)])
                elif first_digit == '6':
                    # For Discover, use only 60, 64, 65 as prefix
                    second_digit = random.choice(['0', '4', '5'])
                    bin_code = '6' + second_digit + ''.join([str(random.randint(0, 9)) for _ in range(4)])
                else:
                    # For Visa (4-series), any random 5 digits will do
                    bin_code = '4' + ''.join([str(random.randint(0, 9)) for _ in range(5)])
            
            if bin_code not in existing_bins and bin_code not in bins_to_verify:
                bins_to_verify.append(bin_code)
        
        # Create a BIN enricher to verify and enrich BINs
        bin_enricher = BinEnricher()
        
        # Process BINs in batches with delay to improve API success rate
        logger.info(f"Verifying {len(bins_to_verify[:count*2])} BINs with Neutrino API")
        enriched_bins = bin_enricher.enrich_bins_batch(bins_to_verify[:count*2])
        
        if not enriched_bins:
            return {
                'status': 'error', 
                'message': 'No BINs could be verified with Neutrino API. Please check your API credentials.'
            }
        
        # Limit to requested count    
        enriched_bins = enriched_bins[:count]
        logger.info(f"Successfully verified {len(enriched_bins)} BINs")
        
        # Add cross-border exploit classification if requested
        if include_cross_border:
            # Get all exploit types with proper query parameterization
            query = text("SELECT id, name FROM exploit_types")
            result = session.execute(query)
            exploit_types = {}
            for row in result.fetchall():
                if len(row) >= 2:  # Ensure row has enough elements
                    exploit_types[row[1]] = row[0]
            
            # If 'cross-border' type doesn't exist, create it
            if 'cross-border' not in exploit_types:
                insert_query = text("""
                    INSERT INTO exploit_types (name, description, created_at) 
                    VALUES (:name, :description, NOW()) 
                    RETURNING id
                """)
                result = session.execute(
                    insert_query, 
                    {
                        'name': 'cross-border', 
                        'description': 'Card used in a different country than its issuing country'
                    }
                )
                exploit_types['cross-border'] = result.fetchone()[0]
                session.commit()
            
            # Set cross-border exploit type to approximately 40% of BINs
            for bin_data in enriched_bins:
                if random.random() < 0.4:
                    # Simulate cross-border fraud by setting a transaction location
                    card_country = bin_data.get("country", "US")
                    
                    # List of common transaction countries different from card's country
                    transaction_countries = ["US", "CA", "GB", "FR", "DE", "IT", "ES", "JP", "SG", "AU"]
                    # Remove the card's own country from the list
                    if card_country in transaction_countries:
                        transaction_countries.remove(card_country)
                    
                    # Select a random transaction country
                    transaction_country = random.choice(transaction_countries)
                    
                    bin_data["transaction_country"] = transaction_country
                    bin_data["exploit_type"] = "cross-border"
                    
                    logger.info(f"BIN {bin_data['BIN']} flagged as cross-border: " + 
                               f"card from {card_country}, transaction in {transaction_country}")
                else:
                    # For other BINs, assign random exploit types
                    available_types = [
                        "skimming", "card-not-present", "track-data-compromise", 
                        "malware-compromise", "raw-dump", "cvv-compromise"
                    ]
                    bin_data["exploit_type"] = random.choice(available_types)
        
        # Save scan history
        scan_record = ScanHistory(
            source="neutrinoapi",
            bins_found=len(enriched_bins),
            bins_classified=len(enriched_bins),
            scan_parameters=f"{{\"count\": {count}, \"include_cross_border\": {str(include_cross_border).lower()}}}"
        )
        session.add(scan_record)
        
        # Process BINs for database
        created = 0
        updated = 0
        
        for bin_data in enriched_bins:
            bin_code = bin_data.get("BIN")
            
            # Skip if no BIN code
            if not bin_code:
                continue
                
            # Check if BIN already exists with parameterized query
            query = text("SELECT id FROM bins WHERE bin_code = :bin_code")
            result = session.execute(query, {'bin_code': bin_code})
            existing_bin = result.fetchone()
            
            if not existing_bin:
                # Create new BIN record with parameterized query
                insert_query = text("""
                    INSERT INTO bins (
                        bin_code, issuer, brand, card_type, prepaid, country, 
                        threeds1_supported, threeds2_supported, patch_status, 
                        transaction_country, is_verified, data_source, created_at, updated_at
                    ) VALUES (
                        :bin_code, :issuer, :brand, :card_type, :prepaid, :country,
                        :threeds1_supported, :threeds2_supported, :patch_status,
                        :transaction_country, TRUE, 'Neutrino API', NOW(), NOW()
                    ) RETURNING id
                """)
                
                result = session.execute(
                    insert_query,
                    {
                        'bin_code': bin_code,
                        'issuer': bin_data.get('issuer', 'Unknown'),
                        'brand': bin_data.get('brand', 'Unknown'),
                        'card_type': bin_data.get('type', 'Unknown'),
                        'prepaid': bin_data.get('prepaid', False),
                        'country': bin_data.get('country', 'XX'),
                        'threeds1_supported': bin_data.get('threeDS1Supported', False),
                        'threeds2_supported': bin_data.get('threeDS2supported', False),
                        'patch_status': bin_data.get('patch_status', 'Unknown'),
                        'transaction_country': bin_data.get('transaction_country')
                    }
                )
                
                bin_id = result.fetchone()[0]
                created += 1
            else:
                # Update existing BIN with parameterized query
                bin_id = existing_bin[0]
                update_query = text("""
                    UPDATE bins SET
                        issuer = :issuer,
                        brand = :brand,
                        card_type = :card_type,
                        prepaid = :prepaid,
                        country = :country,
                        threeds1_supported = :threeds1_supported,
                        threeds2_supported = :threeds2_supported,
                        patch_status = :patch_status,
                        transaction_country = :transaction_country,
                        is_verified = TRUE,
                        data_source = 'Neutrino API',
                        updated_at = NOW()
                    WHERE id = :bin_id
                """)
                
                session.execute(
                    update_query,
                    {
                        'bin_id': bin_id,
                        'issuer': bin_data.get('issuer', 'Unknown'),
                        'brand': bin_data.get('brand', 'Unknown'),
                        'card_type': bin_data.get('type', 'Unknown'),
                        'prepaid': bin_data.get('prepaid', False),
                        'country': bin_data.get('country', 'XX'),
                        'threeds1_supported': bin_data.get('threeDS1Supported', False),
                        'threeds2_supported': bin_data.get('threeDS2supported', False),
                        'patch_status': bin_data.get('patch_status', 'Unknown'),
                        'transaction_country': bin_data.get('transaction_country')
                    }
                )
                updated += 1
            
            # Add exploit data if present
            exploit_type = bin_data.get("exploit_type")
            if exploit_type and exploit_type in exploit_types:
                # Check if this bin-exploit combination already exists
                query = text("""
                    SELECT id, frequency FROM bin_exploits 
                    WHERE bin_id = :bin_id AND exploit_type_id = :exploit_type_id
                """)
                result = session.execute(
                    query, 
                    {
                        'bin_id': bin_id, 
                        'exploit_type_id': exploit_types[exploit_type]
                    }
                )
                existing_exploit = result.fetchone()
                
                if existing_exploit:
                    # Update frequency
                    exploit_id, frequency = existing_exploit
                    update_query = text("""
                        UPDATE bin_exploits SET
                            frequency = :frequency,
                            last_seen = NOW()
                        WHERE id = :exploit_id
                    """)
                    session.execute(
                        update_query, 
                        {
                            'exploit_id': exploit_id, 
                            'frequency': frequency + 1
                        }
                    )
                else:
                    # Insert new exploit record
                    insert_query = text("""
                        INSERT INTO bin_exploits (
                            bin_id, exploit_type_id, frequency, first_seen, last_seen
                        ) VALUES (
                            :bin_id, :exploit_type_id, 1, NOW(), NOW()
                        )
                    """)
                    session.execute(
                        insert_query, 
                        {
                            'bin_id': bin_id, 
                            'exploit_type_id': exploit_types[exploit_type]
                        }
                    )
        
        # Commit all changes
        session.commit()
        
        # Count total BINs
        query = text("SELECT COUNT(*) FROM bins")
        result = session.execute(query)
        total_bins = result.fetchone()[0]
        
        # Return success response
        return {
            'status': 'success',
            'new_bins': created,
            'updated_bins': updated,
            'total_bins': total_bins
        }
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error generating verified BINs: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}
    finally:
        # Always close the session to prevent connection leaks
        session.close()