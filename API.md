# BIN Intelligence System API Documentation

This document provides comprehensive API documentation for the BIN Intelligence System.

## Base URL
```
http://localhost:5000
```

## Authentication
No authentication is required for the current implementation. In production environments, consider implementing API key authentication.

---

## Web Interface Endpoints

### Dashboard
- **GET** `/`
  - **Description**: Main dashboard interface
  - **Response**: HTML dashboard with charts and data tables
  - **Features**: Interactive charts, sortable tables, real-time statistics

### Alternative Dashboard Views
- **GET** `/simple`
  - **Description**: Simplified dashboard view
  - **Response**: HTML with basic functionality

- **GET** `/old`
  - **Description**: Legacy dashboard interface
  - **Response**: HTML with tab-based navigation

---

## API Endpoints

### BIN Data Management

#### Get BIN Data
- **GET** `/api/bins`
- **Description**: Retrieve paginated BIN data with filtering options
- **Query Parameters**:
  - `page` (integer, optional): Page number (default: 1)
  - `per_page` (integer, optional): Records per page (default: 200, max: 1000)
  - `exploitable_only` (boolean, optional): Filter for exploitable BINs only
  - `verified_only` (boolean, optional): Filter for verified BINs only

**Example Request:**
```bash
curl "http://localhost:5000/api/bins?page=1&per_page=50&exploitable_only=true"
```

**Example Response:**
```json
{
  "bins": [
    {
      "BIN": "404138",
      "issuer": "Chase Bank",
      "brand": "VISA",
      "type": "credit",
      "card_level": "STANDARD",
      "prepaid": false,
      "country": "US",
      "transaction_country": null,
      "threeDS1Supported": false,
      "threeDS2supported": false,
      "patch_status": "Exploitable",
      "is_verified": true,
      "exploit_type": "card-not-present"
    }
  ],
  "pagination": {
    "total_bins": 2020,
    "total_pages": 41,
    "current_page": 1,
    "per_page": 50
  }
}
```

### Statistics

#### Get System Statistics
- **GET** `/api/stats`
- **Description**: Retrieve comprehensive system statistics
- **Response**: JSON with counts and distributions

**Example Response:**
```json
{
  "total_bins": 2020,
  "exploitable_bins": 1245,
  "patched_bins": 775,
  "verified_bins": 1890,
  "brands": {
    "VISA": 1012,
    "MASTERCARD": 658,
    "AMERICAN EXPRESS": 245,
    "DISCOVER": 105
  },
  "exploit_types": {
    "card-not-present": 745,
    "false-positive-cvv": 312,
    "no-auto-3ds": 188
  },
  "threeds_support": {
    "threeds1_supported": 1234,
    "threeds2_supported": 1567,
    "both_supported": 987,
    "neither_supported": 453
  },
  "countries": {
    "US": 1567,
    "CA": 234,
    "GB": 156,
    "AU": 63
  }
}
```

### BIN Verification

#### Verify Single BIN
- **GET** `/verify-bin/<bin_code>`
- **Description**: Verify a specific BIN using Neutrino API
- **Parameters**:
  - `bin_code` (string): 6-digit BIN code to verify
- **Response**: JSON with verification results

**Example Request:**
```bash
curl "http://localhost:5000/verify-bin/404138"
```

**Example Response:**
```json
{
  "status": "success",
  "message": "BIN 404138 verified successfully",
  "data": {
    "BIN": "404138",
    "issuer": "Chase Bank",
    "brand": "VISA",
    "type": "credit",
    "prepaid": false,
    "country": "US",
    "threeDS1Supported": false,
    "threeDS2supported": false,
    "patch_status": "Exploitable",
    "data_source": "Neutrino API",
    "is_verified": true,
    "verified_at": "2025-07-04T20:30:12.340000",
    "issuer_website": "https://www.chase.com",
    "issuer_phone": "+1-800-432-3117"
  }
}
```

### Data Generation

#### Generate New BINs
- **GET** `/generate-bins`
- **Description**: Generate and verify new BIN records
- **Query Parameters**:
  - `count` (integer, optional): Number of BINs to generate (default: 10, max: 50)

**Example Request:**
```bash
curl "http://localhost:5000/generate-bins?count=20"
```

**Example Response:**
```json
{
  "status": "success",
  "message": "Successfully generated 20 new verified BINs",
  "bins_added": 20,
  "total_bins": 2040
}
```

### Data Export

#### Export All BINs to CSV
- **GET** `/export-all-bins-csv`
- **Description**: Download all BIN data as CSV file
- **Response**: CSV file download

**CSV Headers:**
```
BIN,Issuer,Brand,Card Type,Card Level,Prepaid,Country,Transaction Country,3DS1 Supported,3DS2 Supported,Patch Status,Verified,Exploit Type
```

#### Export Exploitable BINs to CSV
- **GET** `/export-exploitable-bins-csv`
- **Description**: Download only exploitable BIN data as CSV file
- **Response**: CSV file download (same format as above)

### System Management

#### Refresh Data
- **GET** `/refresh`
- **Description**: Force refresh of BIN intelligence data
- **Query Parameters**:
  - `top_n` (integer, optional): Number of top BINs to process (default: 100)
  - `sample_pages` (integer, optional): Number of pages to sample (default: 5)

**Example Response:**
```json
{
  "status": "success",
  "bins_count": 2020,
  "bins_found": 150,
  "bins_classified": 125,
  "message": "Successfully refreshed data with 150 BINs"
}
```

### Debug and Monitoring

#### System Debug Information
- **GET** `/api/debug`
- **Description**: Get system debug information and database connectivity
- **Response**: JSON with system status

**Example Response:**
```json
{
  "status": "success",
  "database_connected": true,
  "total_bins": 2020,
  "total_exploits": 1245,
  "neutrino_api_configured": true,
  "timestamp": "2025-07-04T20:30:12.340000"
}
```

#### Scan History
- **GET** `/api/scan-history`
- **Description**: Retrieve historical scan information
- **Response**: JSON with scan history data

#### Exploit Types
- **GET** `/api/exploits`
- **Description**: Get all available exploit types
- **Response**: JSON with exploit type definitions

---

## Data Models

### BIN Object
```json
{
  "BIN": "string (6 digits)",
  "issuer": "string",
  "brand": "string (VISA|MASTERCARD|AMERICAN EXPRESS|DISCOVER)",
  "type": "string (credit|debit|prepaid)",
  "card_level": "string (STANDARD|GOLD|PLATINUM|BUSINESS|WORLD)",
  "prepaid": "boolean",
  "country": "string (ISO 2-letter code)",
  "transaction_country": "string (ISO 2-letter code)",
  "threeDS1Supported": "boolean",
  "threeDS2supported": "boolean",
  "patch_status": "string (Exploitable|Patched)",
  "is_verified": "boolean",
  "verified_at": "string (ISO datetime)",
  "data_source": "string",
  "issuer_website": "string",
  "issuer_phone": "string",
  "exploit_type": "string"
}
```

### Exploit Types
- `card-not-present`: BINs vulnerable to card-not-present fraud
- `false-positive-cvv`: BINs with weak CVV verification
- `no-auto-3ds`: BINs lacking automatic 3D Secure authentication

### Card Levels
- `STANDARD`: Basic card tier
- `GOLD`: Mid-tier card with additional benefits
- `PLATINUM`: Premium card tier
- `BUSINESS`: Business/corporate cards
- `WORLD`: Top-tier premium cards

---

## Error Handling

### Standard Error Response
```json
{
  "status": "error",
  "error": "Error description",
  "message": "Detailed error message"
}
```

### Common HTTP Status Codes
- `200 OK`: Successful request
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

### Error Types
- **Validation Errors**: Invalid BIN format, missing parameters
- **Database Errors**: Connection issues, query failures
- **API Errors**: Neutrino API failures, rate limiting
- **System Errors**: Internal application errors

---

## Rate Limiting

### Neutrino API Limits
- Respects Neutrino API rate limits
- Implements exponential backoff for failed requests
- Maximum 60 requests per minute per API key

### Application Limits
- No current rate limiting on application endpoints
- Consider implementing rate limiting for production use

---

## Performance Considerations

### Database Queries
- Optimized SQL queries with proper indexing
- Connection pooling for improved performance
- Pagination to handle large datasets efficiently

### Caching
- No current caching implementation
- Consider Redis for production caching needs

### Pagination
- Default page size: 200 records
- Maximum page size: 1000 records
- Server-side pagination for optimal performance

---

## Security Considerations

### Data Protection
- No sensitive data logged
- API keys stored in environment variables
- Input validation on all endpoints

### HTTPS
- Use HTTPS in production environments
- Secure API key transmission

### Authentication
- Consider implementing API key authentication for production
- Rate limiting by IP address or API key

---

## Integration Examples

### Python Integration
```python
import requests

# Get BIN data
response = requests.get('http://localhost:5000/api/bins?page=1&per_page=50')
bins_data = response.json()

# Verify a BIN
response = requests.get('http://localhost:5000/verify-bin/404138')
verification_result = response.json()

# Get statistics
response = requests.get('http://localhost:5000/api/stats')
stats = response.json()
```

### JavaScript/Node.js Integration
```javascript
// Get BIN data
fetch('/api/bins?page=1&per_page=50')
  .then(response => response.json())
  .then(data => console.log(data));

// Verify a BIN
fetch('/verify-bin/404138')
  .then(response => response.json())
  .then(data => console.log(data));
```

### cURL Examples
```bash
# Get statistics
curl -X GET "http://localhost:5000/api/stats"

# Export exploitable BINs
curl -X GET "http://localhost:5000/export-exploitable-bins-csv" -o exploitable_bins.csv

# Generate new BINs
curl -X GET "http://localhost:5000/generate-bins?count=10"
```

---

## Changelog and Versioning

### API Versioning
- Current version: v2.3.0
- No explicit API versioning in URLs
- Breaking changes documented in CHANGELOG.md

### Recent Changes
- Added table sorting functionality
- Enhanced CSV export capabilities
- Improved error handling and logging
- Added card level classification

---

For more detailed information about system architecture and development guidelines, see:
- [README.md](README.md) - General system documentation
- [CONTRIBUTING.md](CONTRIBUTING.md) - Development guidelines
- [CHANGELOG.md](CHANGELOG.md) - Version history and changes