# 🤖 Autonomous Market Research Agent

A powerful Python-based system that automatically monitors competitors, industry news, and market trends to generate comprehensive weekly research reports. No heavy AI dependencies required!

![Python](https://img.shields.io/badge/python-v3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

## 🌟 Features

- **🕷️ Web Scraping**: Automatically scrapes competitor websites and RSS feeds
- **📊 Data Collection**: Monitors multiple sources simultaneously with configurable frequencies
- **📈 Trend Analysis**: Identifies key topics, keywords, and market movements
- **📋 Report Generation**: Creates comprehensive weekly reports in Markdown format
- **🗄️ Database Storage**: SQLite database for data persistence and historical analysis
- **📧 Email Reports**: Automatic email delivery of reports (optional)
- **⏰ Scheduled Monitoring**: Autonomous operation with customizable schedules
- **🎯 Keyword Tracking**: Smart keyword extraction and frequency analysis
- **🔍 Source Management**: Easy addition and management of monitoring sources

## 🚀 Quick Start

### 1. Installation

```bash
# Clone or download the project
git clone <repository-url>
cd autonomous-market-research-agent

# Install required packages
pip install aiohttp requests beautifulsoup4 feedparser schedule lxml
```

### 2. Setup Configuration

```bash
# Create configuration file
python main.py setup

# Edit the generated config.json with your details
```

### 3. Test the System

```bash
# Run a test collection and report generation
python main.py test
```

### 4. Start Monitoring

```bash
# Start autonomous monitoring
python main.py
```

That's it! Your agent is now running and will:
- Collect data every 6 hours
- Generate reports every Monday at 9 AM
- Save everything to the database and reports folder

## 📋 Requirements

### Required Python Packages
```
aiohttp==3.9.1
requests==2.31.0
beautifulsoup4==4.12.2
feedparser==6.0.10
schedule==1.2.0
lxml==4.9.3
```

### Built-in Python Modules
- sqlite3 (database)
- smtplib (email)
- json, hashlib, datetime, asyncio, etc.

### System Requirements
- Python 3.8+
- Windows/macOS/Linux
- Internet connection
- ~50MB disk space

## ⚙️ Configuration

### Basic Configuration (config.json)

```json
{
  "industry_keywords": [
    "your-industry",
    "competitor-names",
    "product-categories"
  ],
  "news_api_key": "optional-news-api-key",
  "send_email_reports": false,
  "monitoring_sources": [
    {
      "url": "https://competitor.com/blog/feed",
      "type": "rss",
      "company": "Competitor1",
      "frequency": 12
    }
  ]
}
```

### Email Configuration (Optional)

```json
{
  "email_host": "smtp.gmail.com",
  "email_port": 587,
  "email_user": "your-email@gmail.com",
  "email_pass": "your-app-password",
  "report_recipients": "team@company.com",
  "send_email_reports": true
}
```

## 🎯 Usage

### Available Commands

| Command | Description |
|---------|-------------|
| `python main.py` | Start autonomous monitoring |
| `python main.py setup` | Create configuration file |
| `python main.py test` | Run test collection and report |
| `python main.py collect` | Manual data collection |
| `python main.py report` | Generate report now |

### Monitoring Sources

The agent supports multiple source types:

- **RSS Feeds**: `"type": "rss"` - Blog feeds, news feeds, press releases
- **Websites**: `"type": "website"` - Direct website scraping
- **News API**: Automatic industry news collection (requires API key)

### Example Sources to Monitor

```json
"monitoring_sources": [
  {
    "url": "https://competitor1.com/blog/feed",
    "type": "rss",
    "company": "Competitor1",
    "frequency": 12
  },
  {
    "url": "https://competitor2.com/news",
    "type": "website", 
    "company": "Competitor2",
    "frequency": 24
  }
]
```

## 📊 Reports

### Report Structure

Generated reports include:

1. **Executive Summary** - Overview of data collected
2. **Company Analysis** - Individual competitor insights
3. **Industry Trends** - Market-wide developments
4. **Key Topics** - Trending keywords and themes
5. **Source Citations** - Links to all referenced content

### Report Formats

- **Markdown files**: `reports/weekly_report_YYYYMMDD.md`
- **Database storage**: SQLite database for historical analysis
- **Email delivery**: Optional HTML email reports

### Sample Report Output

```markdown
# Market Research Report - August 13, 2025

## Executive Summary
This week's market research covered 40 data points from 3 companies...

## Competitor1 Analysis
**Activity Summary**: 15 items tracked this week.
**Recent Updates**:
- **2025-08-13**: New product launch announcement...

## Industry Trends
**Key Developments**:
- AI adoption increasing in enterprise...
- New regulatory changes affecting...
```

## 🛠️ Customization

### Adding Competitors

1. Find their RSS feed (usually `/feed`, `/rss`, `/blog/feed`)
2. Add to `monitoring_sources` in config.json
3. Restart the agent

### Industry Keywords

Update `industry_keywords` to focus on:
- Your specific industry terms
- Competitor names
- Product categories
- Technology trends relevant to your business

### Scheduling

Default schedule:
- **Data Collection**: Every 6 hours
- **Report Generation**: Every Monday at 9 AM

Modify in `start_monitoring()` function:
```python
schedule.every(3).hours.do(...)  # Every 3 hours
schedule.every().friday.at("17:00").do(...)  # Every Friday 5 PM
```

## 📁 Project Structure

```
autonomous-market-research-agent/
├── main.py                 # Main application file
├── config.json            # Configuration file
├── requirements.txt       # Python dependencies
├── README.md              # This file
├── market_research.db     # SQLite database (auto-created)
└── reports/               # Generated reports folder
    └── weekly_report_*.md
```

## 🔧 Troubleshooting

### Common Issues

**"No module named 'feedparser'"**
```bash
pip install feedparser
```

**"News API returned status 401"**
- Get a free API key from https://newsapi.org
- Add to config.json or set `"news_api_key": ""`

**"No data collected"**
- Check internet connection
- Verify RSS feed URLs are working
- Check `frequency` settings in config

**SSL Certificate errors**
- The agent disables SSL verification by default
- For production, enable SSL in WebScraper class

### Logging

All activities are logged with timestamps:
- INFO: Normal operations
- WARNING: Non-critical issues  
- ERROR: Problems that need attention

Logs appear in console and can be redirected to files.

## 🔒 Privacy & Ethics

### Data Collection
- Only collects publicly available information
- Respects robots.txt when possible
- Uses reasonable request delays
- No personal data collection

### Best Practices
- Monitor only public RSS feeds and websites
- Don't overload servers with frequent requests
- Respect competitor terms of service
- Use collected data responsibly

## 🚀 Advanced Features

### Database Queries

Access the SQLite database directly:
```python
import sqlite3
conn = sqlite3.connect('market_research.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM market_data WHERE company = 'Competitor1'")
```

### Custom Report Templates

Modify the `SimpleReportGenerator` class to customize:
- Report format and structure
- Analysis algorithms
- Keyword extraction methods
- Data filtering

### Integration Options

The agent can be integrated with:
- Slack/Discord bots for notifications
- Business intelligence tools
- CRM systems
- Custom dashboards

## 📈 Performance

### Resource Usage
- **Memory**: ~50-100MB typical usage
- **CPU**: Minimal when idle, moderate during collection
- **Storage**: ~1MB per week of data
- **Network**: ~10-50MB per collection cycle

### Scalability
- Handles 50+ monitoring sources efficiently
- Database supports millions of records
- Async operations for fast data collection
- Configurable request delays to avoid rate limits

## 🤝 Contributing

### Development Setup
```bash
git clone <repository>
cd autonomous-market-research-agent
pip install -r requirements.txt
python main.py test
```

### Adding Features
- New data sources: Extend `WebScraper` class
- Report formats: Modify `SimpleReportGenerator`
- Analysis methods: Add to keyword extraction or trend analysis

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

### Getting Help
- Check this README first
- Review the troubleshooting section
- Examine log output for error details
- Test with `python main.py test`

### Feature Requests
- Document the use case
- Provide example data sources
- Explain expected output format

## 🏷️ Version History

- **v1.0.0** - Initial release with core functionality
- **v1.1.0** - Added email reports and improved error handling
- **v1.2.0** - Enhanced keyword extraction and report formatting

---

**Built with ❤️ for autonomous market research**

*Last updated: August 2025*
