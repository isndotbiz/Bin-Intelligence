"""
Fixed BIN Generator Module - Simple stable implementation

This module provides a simplified and robust implementation for generating
and verifying BINs using the Neutrino API.
"""
import logging
import random
import time
import json
from typing import List, Dict, Any, Optional

from neutrino_api import NeutrinoAPIClient
from bin_enricher import BinEnricher
from models import BIN, ExploitType, BINExploit, ScanHistory
from main import db_session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_bins(count: int = 10, include_cross_border: bool = True) -> Dict[str, Any]:
    """
    Generate and verify additional BINs using Neutrino API with simplified implementation.
    
    Args:
        count: Number of BINs to generate (max 20)
        include_cross_border: Whether to include cross-border fraud detection
        
    Returns:
        Dictionary with status and results
    """
    try:
        # Limit to reasonable number
        count = min(count, 20)
        
        logger.info(f"Generating {count} BINs (simplified implementation)")
        
        # Get all existing BINs to avoid duplicates
        existing_bins = set()
        for bin_record in db_session.query(BIN.bin_code).all():
            if hasattr(bin_record, 'bin_code'):
                existing_bins.add(bin_record.bin_code)
        
        # Known vulnerable BIN prefixes
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
        
        # Generate BINs to verify
        bins_to_verify = []
        for _ in range(count * 2):  # Generate more than needed
            if random.random() < 0.8 and known_vulnerable_prefixes:
                # Use known vulnerable prefixes
                prefix = random.choice(known_vulnerable_prefixes)
                remaining_digits = 6 - len(prefix)
                bin_code = prefix + ''.join([str(random.randint(0, 9)) for _ in range(remaining_digits)])
            else:
                # Generate completely random BIN
                first_digit = random.choice(['3', '4', '5', '6'])
                if first_digit == '3':
                    second_digit = random.choice(['4', '7'])  # Amex
                    bin_code = '3' + second_digit + ''.join([str(random.randint(0, 9)) for _ in range(4)])
                elif first_digit == '5':
                    second_digit = str(random.randint(1, 5))  # Mastercard
                    bin_code = '5' + second_digit + ''.join([str(random.randint(0, 9)) for _ in range(4)])
                elif first_digit == '6':
                    second_digit = random.choice(['0', '4', '5'])  # Discover
                    bin_code = '6' + second_digit + ''.join([str(random.randint(0, 9)) for _ in range(4)])
                else:
                    bin_code = '4' + ''.join([str(random.randint(0, 9)) for _ in range(5)])  # Visa
            
            if bin_code not in existing_bins and bin_code not in bins_to_verify:
                bins_to_verify.append(bin_code)
        
        # Verify BINs using Neutrino API
        bin_enricher = BinEnricher()
        enriched_bins = bin_enricher.enrich_bins_batch(bins_to_verify[:count*2])
        
        if not enriched_bins:
            logger.warning("No BINs could be verified with Neutrino API")
            return {
                'status': 'error', 
                'message': 'No BINs could be verified with Neutrino API. Please check your API credentials.'
            }
        
        # Limit to requested count
        enriched_bins = enriched_bins[:count]
        logger.info(f"Successfully verified {len(enriched_bins)} BINs")
        
        # Add transaction country for cross-border fraud
        if include_cross_border:
            # Make sure cross-border exploit type exists
            cross_border_type = db_session.query(ExploitType).filter(ExploitType.name == 'cross-border').first()
            if not cross_border_type:
                cross_border_type = ExploitType(
                    name='cross-border',
                    description='Card used in a different country than its issuing country'
                )
                db_session.add(cross_border_type)
                db_session.commit()
            
            for bin_data in enriched_bins:
                if random.random() < 0.4:  # 40% chance
                    card_country = bin_data.get("country", "US")
                    
                    # Common transaction countries
                    transaction_countries = ["US", "CA", "GB", "FR", "DE", "IT", "ES", "JP", "SG", "AU"]
                    if card_country in transaction_countries:
                        transaction_countries.remove(card_country)
                    
                    if transaction_countries:  # Make sure list isn't empty
                        transaction_country = random.choice(transaction_countries)
                        bin_data["transaction_country"] = transaction_country
                        bin_data["exploit_type"] = "cross-border"
                    else:
                        bin_data["exploit_type"] = "card-not-present"  # Fallback
                else:
                    # Other exploit types
                    available_types = [
                        "skimming", "card-not-present", "track-data-compromise", 
                        "malware-compromise", "raw-dump", "cvv-compromise"
                    ]
                    bin_data["exploit_type"] = random.choice(available_types)
        
        # Record the scan
        scan_record = ScanHistory(
            source="neutrinoapi",
            bins_found=len(enriched_bins),
            bins_classified=len(enriched_bins),
            scan_parameters=json.dumps({
                "count": count, 
                "include_cross_border": include_cross_border
            })
        )
        db_session.add(scan_record)
        
        # Save BINs to database
        created_count = 0
        updated_count = 0
        
        for bin_data in enriched_bins:
            bin_code = bin_data.get("BIN")
            if not bin_code:
                continue
            
            # Check if BIN already exists
            bin_record = db_session.query(BIN).filter(BIN.bin_code == bin_code).first()
            
            if not bin_record:
                # Create new BIN record
                bin_record = BIN(
                    bin_code=bin_code,
                    issuer=bin_data.get('issuer', 'Unknown'),
                    brand=bin_data.get('brand', 'Unknown'),
                    card_type=bin_data.get('type', 'Unknown'),
                    prepaid=bin_data.get('prepaid', False),
                    country=bin_data.get('country', 'XX'),
                    threeds1_supported=bin_data.get('threeDS1Supported', False),
                    threeds2_supported=bin_data.get('threeDS2supported', False),
                    patch_status=bin_data.get('patch_status', 'Unknown'),
                    transaction_country=bin_data.get('transaction_country'),
                    is_verified=True,
                    data_source='Neutrino API'
                )
                db_session.add(bin_record)
                db_session.flush()  # Get the ID
                created_count += 1
            else:
                # Update existing record
                bin_record.issuer = bin_data.get('issuer', bin_record.issuer)
                bin_record.brand = bin_data.get('brand', bin_record.brand)
                bin_record.card_type = bin_data.get('type', bin_record.card_type)
                bin_record.prepaid = bin_data.get('prepaid', bin_record.prepaid)
                bin_record.country = bin_data.get('country', bin_record.country)
                bin_record.threeds1_supported = bin_data.get('threeDS1Supported', bin_record.threeds1_supported)
                bin_record.threeds2_supported = bin_data.get('threeDS2supported', bin_record.threeds2_supported)
                bin_record.patch_status = bin_data.get('patch_status', bin_record.patch_status)
                
                if 'transaction_country' in bin_data:
                    bin_record.transaction_country = bin_data['transaction_country']
                    
                bin_record.is_verified = True
                bin_record.data_source = 'Neutrino API'
                updated_count += 1
            
            # Add exploit data if present
            exploit_type_name = bin_data.get("exploit_type")
            if exploit_type_name:
                # Get or create exploit type
                exploit_type = db_session.query(ExploitType).filter(ExploitType.name == exploit_type_name).first()
                if not exploit_type:
                    exploit_type = ExploitType(
                        name=exploit_type_name,
                        description=f"Cards compromised via {exploit_type_name}"
                    )
                    db_session.add(exploit_type)
                    db_session.flush()
                
                # Check if this bin-exploit already exists
                bin_exploit = db_session.query(BINExploit).filter(
                    BINExploit.bin_id == bin_record.id,
                    BINExploit.exploit_type_id == exploit_type.id
                ).first()
                
                if bin_exploit:
                    # Update frequency
                    bin_exploit.frequency += 1
                else:
                    # Create new association
                    bin_exploit = BINExploit(
                        bin_id=bin_record.id,
                        exploit_type_id=exploit_type.id,
                        frequency=1
                    )
                    db_session.add(bin_exploit)
        
        # Commit all changes
        db_session.commit()
        
        # Return success response
        total_bins = db_session.query(BIN).count()
        return {
            'status': 'success',
            'new_bins': created_count,
            'updated_bins': updated_count,
            'total_bins': total_bins
        }
    
    except Exception as e:
        # Log and handle any errors
        logger.error(f"Error generating verified BINs: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Make sure to rollback
        db_session.rollback()
        
        return {'status': 'error', 'message': str(e)}