import csv
import json
import logging
import os
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def write_csv(data: List[Dict[str, Any]], filename: str) -> bool:
    """
    Write a list of dictionaries to a CSV file
    
    Args:
        data: List of dictionaries to write
        filename: Path to the output file
        
    Returns:
        True if successful, False otherwise
    """
    if not data:
        logger.warning(f"No data to write to {filename}")
        return False
    
    try:
        with open(filename, 'w', newline='') as csvfile:
            # Get field names from the first dictionary
            fieldnames = list(data[0].keys())
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for row in data:
                writer.writerow(row)
                
        logger.info(f"Successfully wrote {len(data)} rows to {filename}")
        return True
        
    except Exception as e:
        logger.error(f"Error writing to CSV file {filename}: {str(e)}")
        return False

def write_json(data: List[Dict[str, Any]], filename: str) -> bool:
    """
    Write a list of dictionaries to a JSON file
    
    Args:
        data: List of dictionaries to write
        filename: Path to the output file
        
    Returns:
        True if successful, False otherwise
    """
    if not data:
        logger.warning(f"No data to write to {filename}")
        return False
    
    try:
        with open(filename, 'w') as jsonfile:
            json.dump(data, jsonfile, indent=2)
                
        logger.info(f"Successfully wrote {len(data)} records to {filename}")
        return True
        
    except Exception as e:
        logger.error(f"Error writing to JSON file {filename}: {str(e)}")
        return False
