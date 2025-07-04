# Contributing to BIN Intelligence System

Thank you for your interest in contributing to the BIN Intelligence System! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Prerequisites
- Python 3.11 or higher
- PostgreSQL database
- Neutrino API credentials
- Basic understanding of Flask and SQLAlchemy

### Development Setup
1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd bin-intelligence-system
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r pyproject.toml
   ```

4. **Configure environment variables**
   ```bash
   export DATABASE_URL="postgresql://user:pass@localhost:5432/bin_intel"
   export NEUTRINO_API_KEY="your-api-key"
   export NEUTRINO_API_USER_ID="your-user-id"
   ```

5. **Initialize database**
   ```bash
   python main.py  # Creates tables automatically
   ```

## 📝 Development Guidelines

### Code Style
- Follow PEP 8 Python style guidelines
- Use descriptive variable and function names
- Include comprehensive docstrings for all functions and classes
- Maintain consistent indentation (4 spaces)
- Keep line length under 88 characters

### Architecture Principles
- **Single Responsibility**: Each module should have one clear purpose
- **Data Integrity**: Always use authentic data sources (Neutrino API)
- **Error Handling**: Implement comprehensive error handling with proper logging
- **Database Safety**: Use transactions and proper connection management
- **API Rate Limiting**: Respect external API rate limits and implement backoff

### File Organization
```
bin-intelligence-system/
├── main.py                 # Main application entry point
├── models.py              # Database models and schema
├── bin_enricher.py        # BIN data enrichment logic
├── fraud_feed.py          # Fraud feed scraping and analysis
├── neutrino_api.py        # Neutrino API client
├── utils.py               # Utility functions
├── templates/             # HTML templates
│   └── no_tabs_dashboard.html
├── static/                # Static assets (if any)
├── migrations/            # Database migration scripts
└── docs/                  # Additional documentation
```

## 🔧 Making Changes

### Branch Naming Convention
- `feature/description` - New features
- `bugfix/description` - Bug fixes
- `hotfix/description` - Critical fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring

### Commit Message Format
```
type(scope): brief description

Detailed explanation of changes (if needed)

- List specific changes
- Include any breaking changes
- Reference issues if applicable

Closes #123
```

**Types**: feat, fix, docs, style, refactor, test, chore

### Examples
```bash
feat(dashboard): add table sorting functionality

- Implemented clickable column headers
- Added sort indicators with icons
- Maintains compatibility with pagination
- Added client-side sort state management

Closes #45

fix(api): resolve CSV export data type errors

- Fixed boolean value formatting in exports
- Added proper null value handling
- Improved error messages for export failures

Closes #67
```

## 🧪 Testing

### Running Tests
```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=. --cov-report=html

# Run specific test file
python -m pytest tests/test_bin_enricher.py
```

### Writing Tests
- Create tests in the `tests/` directory
- Use descriptive test names: `test_bin_enricher_handles_invalid_bin`
- Mock external API calls (Neutrino API)
- Test both success and failure scenarios
- Include integration tests for database operations

### Test Categories
1. **Unit Tests**: Individual function and method testing
2. **Integration Tests**: Database and API integration testing
3. **End-to-End Tests**: Full workflow testing
4. **Performance Tests**: Database query optimization validation

## 🗃️ Database Changes

### Schema Modifications
1. **Create Migration Script**
   ```python
   # migrations/add_new_field.py
   def add_new_field():
       """Add new field to bins table"""
       with engine.connect() as conn:
           conn.execute(text("ALTER TABLE bins ADD COLUMN new_field VARCHAR(50)"))
   ```

2. **Update Models**
   ```python
   # models.py
   class BIN(Base):
       # ... existing fields
       new_field = Column(String(50), nullable=True)
   ```

3. **Test Migration**
   ```bash
   python migrations/add_new_field.py
   ```

### Database Best Practices
- Always use transactions for multiple operations
- Include proper error handling and rollback
- Test migrations on sample data first
- Document any data transformations required
- Maintain backward compatibility when possible

## 🔌 API Integration

### Adding New Data Sources
1. **Create Client Module**
   ```python
   # new_api_client.py
   class NewAPIClient:
       def __init__(self):
           self.api_key = os.environ.get('NEW_API_KEY')
       
       def lookup_bin(self, bin_code):
           # Implementation
           pass
   ```

2. **Implement Rate Limiting**
   ```python
   import time
   from datetime import datetime, timedelta
   
   class RateLimiter:
       def __init__(self, calls_per_minute=60):
           self.calls_per_minute = calls_per_minute
           self.calls = []
   ```

3. **Add Error Handling**
   ```python
   try:
       response = api_client.lookup_bin(bin_code)
   except requests.exceptions.RequestException as e:
       logger.error(f"API request failed: {e}")
       return None
   ```

## 🎨 Frontend Development

### Dashboard Components
- Use Bootstrap 5.3 for styling consistency
- Maintain dark theme throughout interface
- Implement responsive design principles
- Use Chart.js for data visualizations

### JavaScript Guidelines
- Use vanilla JavaScript (no external frameworks)
- Implement proper error handling for API calls
- Use modern ES6+ features where appropriate
- Comment complex logic thoroughly

### Adding New Features
1. **Backend API Endpoint**
   ```python
   @app.route('/api/new-feature')
   def new_feature():
       try:
           # Implementation
           return jsonify({'status': 'success', 'data': result})
       except Exception as e:
           return jsonify({'status': 'error', 'message': str(e)}), 500
   ```

2. **Frontend Integration**
   ```javascript
   function loadNewFeature() {
       fetch('/api/new-feature')
           .then(response => response.json())
           .then(data => {
               if (data.status === 'success') {
                   // Handle success
               } else {
                   // Handle error
               }
           })
           .catch(error => console.error('Error:', error));
   }
   ```

## 📊 Performance Considerations

### Database Optimization
- Use proper indexing for frequently queried columns
- Implement pagination for large datasets
- Use connection pooling for database connections
- Monitor query performance and optimize slow queries

### API Rate Management
- Implement exponential backoff for failed requests
- Cache API responses when appropriate
- Batch requests when possible
- Monitor API usage against rate limits

### Frontend Performance
- Minimize DOM manipulation operations
- Use efficient sorting and filtering algorithms
- Implement lazy loading for large datasets
- Optimize chart rendering performance

## 🚀 Deployment

### Environment Configuration
- Use environment variables for all configuration
- Never commit sensitive information (API keys, passwords)
- Document all required environment variables
- Provide example configuration files

### Production Checklist
- [ ] All tests passing
- [ ] Database migrations tested
- [ ] API credentials configured
- [ ] Error logging implemented
- [ ] Performance benchmarks met
- [ ] Security review completed

## 🐛 Bug Reports

### Bug Report Template
```markdown
**Bug Description**
Clear and concise description of the bug.

**Steps to Reproduce**
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

**Expected Behavior**
What you expected to happen.

**Actual Behavior**
What actually happened.

**Environment**
- OS: [e.g. iOS]
- Browser: [e.g. chrome, safari]
- Version: [e.g. 22]

**Additional Context**
Add any other context about the problem here.
```

## 💡 Feature Requests

### Feature Request Template
```markdown
**Feature Description**
Clear and concise description of the proposed feature.

**Problem Statement**
What problem does this feature solve?

**Proposed Solution**
How would you like this feature to work?

**Alternatives Considered**
Other solutions you've considered.

**Additional Context**
Any other context or screenshots about the feature request.
```

## 🔒 Security Guidelines

### Data Handling
- Never log sensitive information (API keys, BIN data)
- Implement proper input validation
- Use parameterized queries to prevent SQL injection
- Sanitize all user inputs

### API Security
- Validate all API responses before processing
- Implement proper authentication for API endpoints
- Use HTTPS for all external API communications
- Rotate API keys regularly

### Database Security
- Use connection encryption
- Implement proper access controls
- Regular security audits of database permissions
- Backup and recovery procedures

## 📚 Documentation

### Code Documentation
- Document all public functions and classes
- Include usage examples in docstrings
- Maintain up-to-date API documentation
- Document any complex algorithms or business logic

### User Documentation
- Keep README.md current with latest features
- Update CHANGELOG.md for all releases
- Provide clear installation and setup instructions
- Include troubleshooting guides

## 🎯 Pull Request Process

1. **Pre-submission Checklist**
   - [ ] Code follows style guidelines
   - [ ] Tests written and passing
   - [ ] Documentation updated
   - [ ] CHANGELOG.md updated
   - [ ] No merge conflicts

2. **Pull Request Description**
   - Clearly describe the changes made
   - Reference any related issues
   - Include screenshots for UI changes
   - List any breaking changes

3. **Review Process**
   - Address all review comments
   - Update documentation as needed
   - Ensure CI/CD pipeline passes
   - Squash commits before merging

## 🤝 Community Guidelines

### Code of Conduct
- Be respectful and inclusive
- Provide constructive feedback
- Help newcomers to the project
- Focus on the technical aspects

### Communication
- Use clear and professional language
- Be patient with questions and discussions
- Provide context for decisions and changes
- Document important discussions

## 📞 Getting Help

### Resources
- **Documentation**: Check README.md and CHANGELOG.md
- **Issues**: Search existing issues before creating new ones
- **Discussions**: Use GitHub Discussions for questions
- **Code Review**: Request reviews from maintainers

### Contact
- Create an issue for bugs or feature requests
- Use discussions for general questions
- Tag maintainers for urgent issues
- Follow up on stale pull requests

---

Thank you for contributing to the BIN Intelligence System! Your contributions help make fraud prevention more effective and accessible.