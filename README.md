# BIN Intelligence System

A Python-based system that tracks, classifies, and analyzes exploited credit card BINs (Bank Identification Numbers) from public sources. The system scrapes card-dump feeds, classifies exploits by type based on contextual keywords, and enriches the data with issuer information and 3DS support status.

## Features

- Scrapes public card-dump feeds (e.g., Pastebin) for BINs and exploit data
- Extracts PANs (Primary Account Numbers) and their BINs using regex
- Classifies BINs by exploit type using keyword detection
- Filters out BINs without meaningful classification
- Focuses only on major card networks (3, 4, 5, or 6 series BINs):
  - 3-series: American Express
  - 4-series: Visa
  - 5-series: MasterCard
  - 6-series: Discover
- Enriches BINs with issuer information
- Checks 3DS support and determines patch status
- Provides a shareable fraud intelligence dashboard
- Outputs structured data to CSV and JSON files

## Classification Keywords

The system classifies exploits into the following categories based on keywords found in the text:

| Keywords | Exploit Type |
|----------|-------------|
| "skim", "atm" | skimming |
| "cnp", "ecom", "online" | card-not-present |
| "gift", "voucher" | gift-card-fraud |
| "chargeback", "fraud" | unauthorized-chargebacks |
| "dump", "track" | track-data-compromise |
| "malware" | malware-compromise |
| "raw" | raw-dump |
| "fullz" | identity-theft |
| "cvv" | cvv-compromise |

If multiple exploit types are detected, the most frequent one is assigned to the BIN.

## Patch Status Logic

The system determines a BIN's patch status based on its 3DS (3-D Secure) support:

- **Patched**: If the BIN supports either 3DS version 1 or 3DS version 2
- **Exploitable**: If the BIN doesn't support any version of 3DS

This logic is implemented in the `_determine_patch_status` method of the `BinEnricher` class:

```python
def _determine_patch_status(self, threeDS1Supported: bool, threeDS2supported: bool) -> str:
    """
    Determine the patch status based on 3DS support
    
    Args:
        threeDS1Supported: Whether 3DS v1 is supported
        threeDS2supported: Whether 3DS v2 is supported
        
    Returns:
        "Patched" or "Exploitable"
    """
    if threeDS1Supported or threeDS2supported:
        return "Patched"
    else:
        return "Exploitable"
```

3DS support acts as a security measure that helps prevent unauthorized transactions, making BINs with 3DS support less vulnerable to exploitation.

## Configuration Parameters

The system's behavior can be configured using the following parameters in `main.py`:

- `top_n`: Number of top BINs to process, sorted by frequency (default: 100)
- `sample_pages`: Number of pages/posts to sample from each source (default: 5)

Example usage:

```python
# Process top 200 BINs, sampling 10 pages
enriched_bins = process_exploited_bins(top_n=200, sample_pages=10)
```

## Output Format

The system outputs two files:

1. `exploited_bins.csv`: A CSV file containing the enriched BIN data
2. `exploited_bins.json`: A JSON file containing the same data

Both files include the following fields for each BIN:
```
BIN, exploit_type, patch_status, issuer, brand, type, prepaid, country, threeDS1Supported, threeDS2supported
```

Note: Only BINs that have been classified with an exploit type are included in the output. BINs without meaningful classification are discarded during processing.
