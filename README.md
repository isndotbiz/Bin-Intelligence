# BIN Intelligence System

A comprehensive Python-powered BIN Intelligence System that tracks, classifies, and analyzes exploited credit card BINs from verified sources. The system provides advanced fraud intelligence through real-time verification, data enrichment, and detailed vulnerability analysis specifically for e-commerce protection.

## 🚀 Features

### Core Functionality
- **Real-time BIN Verification**: Integration with Neutrino API for authentic BIN data
- **E-commerce Fraud Detection**: Focus on card-not-present, false-positive CVV, and no-Auto-3DS vulnerabilities
- **Advanced Data Enrichment**: Automatic enrichment of BIN data with issuer information and 3DS support
- **Comprehensive Dashboard**: Interactive web interface with charts and data visualization
- **Export Capabilities**: CSV export for all BINs and exploitable BINs specifically

### Technical Features
- **Database Management**: PostgreSQL with SQLAlchemy ORM
- **Data Processing**: Python-based fraud feed analysis and BIN classification
- **Web Interface**: Flask-based dashboard with Bootstrap dark theme
- **API Integration**: Neutrino API for real-world BIN verification
- **Pagination & Sorting**: Client-side table sorting and server-side pagination
- **Real-time Updates**: Dynamic data loading and verification

## 🛠️ Technology Stack

- **Backend**: Python 3.11, Flask, SQLAlchemy
- **Database**: PostgreSQL
- **Frontend**: HTML5, Bootstrap 5.3, Chart.js
- **APIs**: Neutrino API for BIN verification
- **Server**: Gunicorn WSGI server
- **Data Processing**: Trafilatura for web scraping

## 🏗️ Architecture

### Database Schema
- **BINs Table**: Core BIN data with issuer, brand, card type, and security features
- **Exploit Types**: Classification of vulnerability types
- **BIN Exploits**: Association table linking BINs to exploit types
- **Scan History**: Historical data of system scans

### Key Components
- **BIN Enricher**: Processes and enriches BIN data using Neutrino API
- **Fraud Feed Scraper**: Analyzes public sources for compromised BINs
- **Neutrino API Client**: Handles API communication and data transformation
- **Dashboard**: Web interface for data visualization and management

## 📋 Prerequisites

- Python 3.11+
- PostgreSQL database
- Neutrino API credentials (for BIN verification)

## 🚀 Installation & Setup

### Environment Setup
1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd bin-intelligence-system
   ```

2. **Set up environment variables**
   ```bash
   export DATABASE_URL="postgresql://username:password@host:port/database"
   export NEUTRINO_API_KEY="your-neutrino-api-key"
   export NEUTRINO_API_USER_ID="your-neutrino-user-id"
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### Database Setup
The system automatically creates database tables on first run. No manual migration is required.

### Running the Application
```bash
# Start the web application
gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app

# Or run the BIN intelligence workflow
python main.py
```

## 📊 Usage

### Web Dashboard
Navigate to `http://localhost:5000` to access the dashboard featuring:
- **Statistics Overview**: Total BINs, exploit types, and patch status
- **Interactive Charts**: Visual representation of data by brand, 3DS support, and exploit types
- **BIN Data Table**: Sortable table with filtering options
- **Export Functions**: Download data as CSV files
- **Real-time Verification**: Verify individual BINs using Neutrino API

### API Endpoints
- `GET /api/bins` - Retrieve BIN data with pagination
- `GET /api/stats` - Get system statistics
- `GET /verify-bin/<bin_code>` - Verify a specific BIN
- `GET /export-all-bins-csv` - Export all BINs to CSV
- `GET /export-exploitable-bins-csv` - Export exploitable BINs to CSV

### Key Features
1. **BIN Verification**: Enter a 6-digit BIN to get real-time verification
2. **Data Filtering**: Filter by exploitable BINs or verified status
3. **Table Sorting**: Click column headers to sort data
4. **Data Export**: Download filtered or complete datasets
5. **Pagination**: Navigate through large datasets efficiently

## 🔒 Security & Compliance

### Data Sources
- **Neutrino API**: Primary source for authentic BIN data
- **Real-world Data Only**: No synthetic or mock data is used
- **Verified Sources**: All data comes from legitimate fraud intelligence feeds

### Security Features
- **3DS Analysis**: Comprehensive 3D Secure support detection
- **Patch Status Tracking**: Identifies exploitable vs. patched BINs
- **Fraud Classification**: Categorizes e-commerce specific vulnerabilities

## 🗃️ Database Schema

### BINs Table
- `bin_code`: 6-digit Bank Identification Number
- `issuer`: Card issuing bank/institution
- `brand`: Card network (VISA, MASTERCARD, AMEX, DISCOVER)
- `card_type`: Type of card (credit, debit, prepaid)
- `card_level`: Card tier (STANDARD, GOLD, PLATINUM, etc.)
- `country`: Issuing country (ISO code)
- `threeds1_supported`: 3D Secure v1 support
- `threeds2_supported`: 3D Secure v2 support
- `patch_status`: Security status (Exploitable/Patched)
- `is_verified`: Verification status via Neutrino API

### Exploit Classification
- **card-not-present**: BINs vulnerable to CNP fraud
- **false-positive-cvv**: BINs with weak CVV verification
- **no-auto-3ds**: BINs lacking automatic 3D Secure

## 🔧 Configuration

### Environment Variables
- `DATABASE_URL`: PostgreSQL connection string
- `NEUTRINO_API_KEY`: Neutrino API authentication key
- `NEUTRINO_API_USER_ID`: Neutrino API user identifier
- `FLASK_SECRET_KEY`: Flask session secret (optional)

### Performance Settings
- Default pagination: 200 records per page
- API timeout: 10 seconds
- Database connection pooling enabled
- Automatic connection retry with exponential backoff

## 🚀 Deployment

### Production Deployment
1. Set up PostgreSQL database
2. Configure environment variables
3. Install dependencies
4. Run database migrations (automatic)
5. Start Gunicorn server

### Replit Deployment
The application is optimized for Replit deployment with:
- Automatic workflow detection
- Built-in database support
- Environment variable management
- One-click deployment capability

## 📈 Monitoring & Logging

### Logging
- Comprehensive logging throughout the application
- Database operation tracking
- API call monitoring
- Error handling and reporting

### Metrics
- Total BINs processed
- Verification success rates
- Database performance metrics
- API response times

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Make changes following the coding standards
4. Test thoroughly
5. Submit a pull request

### Code Standards
- Python PEP 8 compliance
- Comprehensive error handling
- Database transaction management
- API rate limiting respect

## 📄 License

This project is intended for educational and legitimate fraud prevention purposes only. Use responsibly and in accordance with applicable laws and regulations.

## 🆘 Support

For technical support or questions:
1. Check the CHANGELOG for recent updates
2. Review the database logs for error details
3. Verify API credentials and connectivity
4. Ensure all environment variables are set correctly

## 🔗 API Documentation

### Neutrino API Integration
The system integrates with Neutrino API's BIN Lookup service for real-time verification:
- Endpoint: `https://neutrinoapi.net/bin-lookup`
- Authentication: API key and user ID required
- Rate limits: Respected through proper request handling
- Response caching: Implemented for optimal performance

---

**Note**: This system is designed exclusively for legitimate fraud prevention and educational purposes. Always ensure compliance with applicable laws and regulations when deploying in production environments.