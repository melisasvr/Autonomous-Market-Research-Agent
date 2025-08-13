#!/usr/bin/env python3
"""
Lightweight Autonomous Market Research Agent
A simplified system for monitoring competitors and generating reports without heavy AI dependencies.
"""

import asyncio
import aiohttp
import sys
import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
import feedparser
import schedule
import time
import logging
from pathlib import Path
import re
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Fix for Windows asyncio event loop issue
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# SQLite datetime adapter for Python 3.12+
def adapt_datetime(dt):
    return dt.isoformat()

def convert_datetime(s):
    return datetime.fromisoformat(s.decode('utf-8'))

sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter('timestamp', convert_datetime)

@dataclass
class DataSource:
    """Represents a data source to monitor"""
    url: str
    source_type: str  # 'website', 'rss', 'news'
    company: str
    frequency: int = 24  # hours
    last_checked: Optional[datetime] = None
    is_active: bool = True

@dataclass
class MarketData:
    """Represents collected market data"""
    id: str
    source: str
    company: str
    title: str
    content: str
    url: str
    timestamp: datetime
    data_type: str
    keywords: List[str] = None

class DatabaseManager:
    """Manages SQLite database operations"""
    
    def __init__(self, db_path: str = "market_research.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()
        
        # Data sources table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_sources (
                url TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                company TEXT NOT NULL,
                frequency INTEGER DEFAULT 24,
                last_checked timestamp,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Market data table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_data (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                company TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                url TEXT NOT NULL,
                timestamp timestamp NOT NULL,
                data_type TEXT NOT NULL,
                keywords TEXT
            )
        ''')
        
        # Reports table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                report_date TEXT NOT NULL,
                content TEXT NOT NULL,
                sources_cited TEXT NOT NULL,
                created_at timestamp NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_data_source(self, source: DataSource):
        """Add a new data source"""
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO data_sources 
            (url, source_type, company, frequency, last_checked, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            source.url, source.source_type, source.company,
            source.frequency, source.last_checked, source.is_active
        ))
        
        conn.commit()
        conn.close()
    
    def get_sources_to_check(self) -> List[DataSource]:
        """Get sources that need to be checked"""
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM data_sources 
            WHERE is_active = 1 AND (
                last_checked IS NULL OR 
                datetime(last_checked) < datetime('now', '-' || frequency || ' hours')
            )
        ''')
        
        sources = []
        for row in cursor.fetchall():
            last_checked = row[4] if row[4] else None
            sources.append(DataSource(
                url=row[0], source_type=row[1], company=row[2],
                frequency=row[3], last_checked=last_checked, is_active=bool(row[5])
            ))
        
        conn.close()
        return sources
    
    def store_market_data(self, data: MarketData):
        """Store market data"""
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()
        
        keywords_json = json.dumps(data.keywords) if data.keywords else None
        
        cursor.execute('''
            INSERT OR REPLACE INTO market_data
            (id, source, company, title, content, url, timestamp, data_type, keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.id, data.source, data.company, data.title, data.content,
            data.url, data.timestamp, data.data_type, keywords_json
        ))
        
        conn.commit()
        conn.close()
    
    def get_recent_data(self, days: int = 7) -> List[MarketData]:
        """Get market data from the last N days"""
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM market_data 
            WHERE datetime(timestamp) > datetime('now', '-' || ? || ' days')
            ORDER BY timestamp DESC
        ''', (days,))
        
        data_list = []
        for row in cursor.fetchall():
            keywords = json.loads(row[8]) if row[8] else []
            
            data_list.append(MarketData(
                id=row[0], source=row[1], company=row[2], title=row[3],
                content=row[4], url=row[5], 
                timestamp=row[6],
                data_type=row[7], keywords=keywords
            ))
        
        conn.close()
        return data_list

class WebScraper:
    """Handles web scraping operations"""
    
    def __init__(self):
        self.session = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    async def __aenter__(self):
        # Use default resolver to avoid aiodns issues
        connector = aiohttp.TCPConnector(
            ssl=False,  # Disable SSL verification for simplicity
            use_dns_cache=False  # Disable DNS cache
        )
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(headers=self.headers, connector=connector, timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def extract_keywords(self, text: str) -> List[str]:
        """Simple keyword extraction using word frequency"""
        # Remove HTML and normalize text
        text = re.sub(r'<[^>]+>', '', text.lower())
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text)
        
        # Count word frequency
        word_count = {}
        for word in words:
            if word not in ['this', 'that', 'with', 'have', 'they', 'been', 'said', 'from', 'they', 'were', 'will']:
                word_count[word] = word_count.get(word, 0) + 1
        
        # Return top 10 most frequent words
        return [word for word, count in sorted(word_count.items(), key=lambda x: x[1], reverse=True)[:10]]
    
    async def scrape_website(self, url: str, company: str) -> List[MarketData]:
        """Scrape a website for relevant content"""
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"HTTP {response.status} for {url}")
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()
                
                # Extract main content
                main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=['content', 'main'])
                
                if main_content:
                    content_tags = main_content.find_all(['p', 'h1', 'h2', 'h3', 'h4'])
                else:
                    content_tags = soup.find_all(['p', 'h1', 'h2', 'h3'])
                
                content = ' '.join([tag.get_text(strip=True) for tag in content_tags])
                
                if len(content) < 100:  # Skip if too little content
                    logger.info(f"Insufficient content from {url}")
                    return []
                
                # Create data entry
                data_id = hashlib.md5(f"{url}_{content[:100]}".encode()).hexdigest()
                keywords = self.extract_keywords(content)
                
                return [MarketData(
                    id=data_id,
                    source=url,
                    company=company,
                    title=soup.title.string if soup.title else "Website Content",
                    content=content[:3000],  # Limit content length
                    url=url,
                    timestamp=datetime.now(),
                    data_type="website",
                    keywords=keywords
                )]
                
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return []
    
    async def scrape_rss_feed(self, url: str, company: str) -> List[MarketData]:
        """Scrape RSS feed for new articles"""
        try:
            # Use requests for RSS since feedparser doesn't work well with aiohttp
            response = requests.get(url, headers=self.headers, timeout=30)
            feed = feedparser.parse(response.content)
            
            data_list = []
            
            for entry in feed.entries[:15]:  # Limit to 15 most recent
                # Check if entry is from last week
                entry_date = datetime.now()
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    entry_date = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    entry_date = datetime(*entry.updated_parsed[:6])
                
                if entry_date < datetime.now() - timedelta(days=7):
                    continue
                
                content = ""
                if hasattr(entry, 'summary'):
                    content = entry.summary
                elif hasattr(entry, 'description'):
                    content = entry.description
                elif hasattr(entry, 'content'):
                    content = entry.content[0].value if entry.content else ""
                
                if len(content) < 50:
                    continue
                
                data_id = hashlib.md5(f"{entry.link}_{entry.title}".encode()).hexdigest()
                keywords = self.extract_keywords(content)
                
                data_list.append(MarketData(
                    id=data_id,
                    source=url,
                    company=company,
                    title=entry.title,
                    content=content[:2000],
                    url=entry.link,
                    timestamp=entry_date,
                    data_type="rss",
                    keywords=keywords
                ))
            
            return data_list
            
        except Exception as e:
            logger.error(f"Error scraping RSS {url}: {e}")
            return []

class NewsAggregator:
    """Aggregates news from various sources"""
    
    def __init__(self, news_api_key: str = None):
        self.news_api_key = news_api_key
        self.headers = {'User-Agent': 'Mozilla/5.0 (compatible; MarketResearchBot/1.0)'}
    
    async def get_industry_news(self, keywords: List[str]) -> List[MarketData]:
        """Get industry news using News API or free news sources"""
        news_data = []
        
        if self.news_api_key:
            news_data.extend(await self._get_news_api_data(keywords))
        
        # Add free news sources
        news_data.extend(await self._get_free_news_sources(keywords))
        
        return news_data
    
    async def _get_news_api_data(self, keywords: List[str]) -> List[MarketData]:
        """Get news from News API"""
        try:
            query = " OR ".join(keywords[:3])  # Limit query length
            url = f"https://newsapi.org/v2/everything"
            params = {
                'q': query,
                'apiKey': self.news_api_key,
                'pageSize': 30,
                'sortBy': 'publishedAt',
                'language': 'en'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"News API returned status {response.status}")
                        return []
                    
                    data = await response.json()
                    
                    news_data = []
                    for article in data.get('articles', []):
                        # Skip old articles
                        article_date = datetime.fromisoformat(article['publishedAt'].replace('Z', '+00:00'))
                        if article_date < datetime.now().replace(tzinfo=article_date.tzinfo) - timedelta(days=7):
                            continue
                        
                        if not article.get('description'):
                            continue
                        
                        data_id = hashlib.md5(article['url'].encode()).hexdigest()
                        
                        news_data.append(MarketData(
                            id=data_id,
                            source=article['source']['name'],
                            company="Industry",
                            title=article['title'],
                            content=article['description'],
                            url=article['url'],
                            timestamp=article_date.replace(tzinfo=None),
                            data_type="news"
                        ))
                    
                    return news_data
                    
        except Exception as e:
            logger.error(f"Error fetching industry news from News API: {e}")
            return []
    
    async def _get_free_news_sources(self, keywords: List[str]) -> List[MarketData]:
        """Get news from free RSS sources"""
        free_sources = [
            "https://techcrunch.com/feed/",
            "https://www.theverge.com/rss/index.xml",
            "https://feeds.feedburner.com/venturebeat/SZYF"
        ]
        
        news_data = []
        scraper = WebScraper()
        
        async with scraper:
            for source_url in free_sources:
                try:
                    source_data = await scraper.scrape_rss_feed(source_url, "Industry")
                    # Filter by keywords
                    for item in source_data:
                        item_text = f"{item.title} {item.content}".lower()
                        if any(keyword.lower() in item_text for keyword in keywords):
                            news_data.append(item)
                except Exception as e:
                    logger.error(f"Error getting news from {source_url}: {e}")
        
        return news_data[:20]  # Limit results

class SimpleReportGenerator:
    """Generates market analysis reports using simple text processing"""
    
    def generate_weekly_report(self, data_list: List[MarketData]) -> Dict:
        """Generate a comprehensive weekly report"""
        
        # Organize data by company
        company_data = {}
        for data in data_list:
            if data.company not in company_data:
                company_data[data.company] = []
            company_data[data.company].append(data)
        
        # Generate report sections
        sections = []
        sources_cited = set()
        
        # Executive Summary
        summary_content = self._generate_executive_summary(data_list)
        sections.append(("Executive Summary", summary_content))
        
        # Company-specific analysis
        for company, company_items in company_data.items():
            if company == "Industry":
                continue
            
            analysis = self._analyze_company_data(company, company_items)
            sections.append((f"{company} Analysis", analysis))
            
            # Add sources
            for item in company_items:
                sources_cited.add(item.url)
        
        # Industry trends
        if "Industry" in company_data:
            trends = self._analyze_industry_trends(company_data["Industry"])
            sections.append(("Industry Trends", trends))
            
            for item in company_data["Industry"]:
                sources_cited.add(item.url)
        
        # Top Keywords Analysis
        keyword_analysis = self._analyze_keywords(data_list)
        sections.append(("Key Topics This Week", keyword_analysis))
        
        # Compile final report
        report_content = f"# Market Research Report - {datetime.now().strftime('%B %d, %Y')}\n\n"
        report_content += "\n\n".join([f"## {title}\n\n{content}" for title, content in sections])
        
        return {
            "content": report_content,
            "sources_cited": list(sources_cited),
            "generated_at": datetime.now().isoformat(),
            "data_points": len(data_list)
        }
    
    def _generate_executive_summary(self, data_list: List[MarketData]) -> str:
        """Generate executive summary using simple analysis"""
        total_items = len(data_list)
        companies = set(item.company for item in data_list if item.company != "Industry")
        
        # Count by data type
        type_counts = {}
        for item in data_list:
            type_counts[item.data_type] = type_counts.get(item.data_type, 0) + 1
        
        summary = f"This week's market research covered {total_items} data points from {len(companies)} companies and industry sources.\n\n"
        
        if type_counts:
            summary += "Data sources breakdown:\n"
            for data_type, count in type_counts.items():
                summary += f"- {data_type.title()}: {count} items\n"
            summary += "\n"
        
        # Recent activity summary
        recent_items = sorted(data_list, key=lambda x: x.timestamp, reverse=True)[:5]
        summary += "Most recent developments:\n"
        for item in recent_items:
            summary += f"- **{item.company}**: {item.title[:100]}{'...' if len(item.title) > 100 else ''}\n"
        
        return summary
    
    def _analyze_company_data(self, company: str, data_items: List[MarketData]) -> str:
        """Analyze data for a specific company"""
        analysis = f"**Activity Summary**: {len(data_items)} items tracked this week.\n\n"
        
        # Recent items
        recent_items = sorted(data_items, key=lambda x: x.timestamp, reverse=True)[:5]
        
        analysis += "**Recent Updates:**\n"
        for item in recent_items:
            date_str = item.timestamp.strftime('%Y-%m-%d')
            analysis += f"- **{date_str}**: {item.title}\n"
            if len(item.content) > 100:
                analysis += f"  *Summary*: {item.content[:200]}...\n"
            analysis += f"  *Source*: [Link]({item.url})\n\n"
        
        # Top keywords for this company
        all_keywords = []
        for item in data_items:
            if item.keywords:
                all_keywords.extend(item.keywords)
        
        if all_keywords:
            keyword_freq = {}
            for keyword in all_keywords:
                keyword_freq[keyword] = keyword_freq.get(keyword, 0) + 1
            
            top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:8]
            analysis += f"**Key Topics**: {', '.join([kw for kw, freq in top_keywords])}\n"
        
        return analysis
    
    def _analyze_industry_trends(self, industry_data: List[MarketData]) -> str:
        """Analyze industry trends"""
        analysis = f"**Industry Coverage**: {len(industry_data)} news items and updates tracked.\n\n"
        
        # Top sources
        source_count = {}
        for item in industry_data:
            source = item.source
            source_count[source] = source_count.get(source, 0) + 1
        
        top_sources = sorted(source_count.items(), key=lambda x: x[1], reverse=True)[:5]
        analysis += "**Top News Sources:**\n"
        for source, count in top_sources:
            analysis += f"- {source}: {count} articles\n"
        analysis += "\n"
        
        # Recent headlines
        recent_items = sorted(industry_data, key=lambda x: x.timestamp, reverse=True)[:8]
        analysis += "**Recent Industry Headlines:**\n"
        for item in recent_items:
            date_str = item.timestamp.strftime('%m-%d')
            analysis += f"- **{date_str}**: {item.title}\n"
            if item.url:
                analysis += f"  [Read more]({item.url})\n"
        
        return analysis
    
    def _analyze_keywords(self, data_list: List[MarketData]) -> str:
        """Analyze top keywords across all data"""
        all_keywords = []
        for item in data_list:
            if item.keywords:
                all_keywords.extend(item.keywords)
        
        if not all_keywords:
            return "No keyword data available."
        
        keyword_freq = {}
        for keyword in all_keywords:
            keyword_freq[keyword] = keyword_freq.get(keyword, 0) + 1
        
        top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:15]
        
        analysis = "**Most Mentioned Topics:**\n"
        for keyword, freq in top_keywords:
            analysis += f"- **{keyword}**: mentioned {freq} times\n"
        
        return analysis

class MarketResearchAgent:
    """Main agent orchestrating the market research process"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.db_manager = DatabaseManager()
        self.report_generator = SimpleReportGenerator()
        self.news_aggregator = NewsAggregator(self.config.get('news_api_key'))
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config file {config_path} not found. Using default configuration.")
            return {
                'industry_keywords': ['technology', 'startup', 'innovation'],
                'send_email_reports': False
            }
    
    def setup_monitoring(self):
        """Set up data sources for monitoring"""
        # Example data sources - customize as needed
        sources = [
            DataSource("https://techcrunch.com/feed/", "rss", "TechCrunch", 12),
            DataSource("https://www.theverge.com/rss/index.xml", "rss", "TheVerge", 12),
            DataSource("https://feeds.feedburner.com/venturebeat/SZYF", "rss", "VentureBeat", 12),
            # Add your competitor websites here
            # DataSource("https://competitor1.com", "website", "Competitor1", 24),
            # DataSource("https://competitor2.com/news", "rss", "Competitor2", 12),
        ]
        
        for source in sources:
            self.db_manager.add_data_source(source)
        
        logger.info(f"Set up {len(sources)} monitoring sources")
    
    async def collect_data(self):
        """Collect data from all configured sources"""
        sources = self.db_manager.get_sources_to_check()
        logger.info(f"Checking {len(sources)} data sources")
        
        all_data = []
        
        async with WebScraper() as scraper:
            for source in sources:
                try:
                    logger.info(f"Processing {source.source_type} source: {source.url}")
                    
                    if source.source_type == "website":
                        data = await scraper.scrape_website(source.url, source.company)
                    elif source.source_type == "rss":
                        data = await scraper.scrape_rss_feed(source.url, source.company)
                    else:
                        continue
                    
                    # Store data
                    for item in data:
                        self.db_manager.store_market_data(item)
                        all_data.append(item)
                    
                    # Update last checked timestamp
                    source.last_checked = datetime.now()
                    self.db_manager.add_data_source(source)
                    
                    logger.info(f"Collected {len(data)} items from {source.url}")
                    
                except Exception as e:
                    logger.error(f"Error processing source {source.url}: {e}")
        
        # Collect industry news
        if self.config.get('industry_keywords'):
            try:
                logger.info("Collecting industry news...")
                news_data = await self.news_aggregator.get_industry_news(self.config['industry_keywords'])
                for item in news_data:
                    self.db_manager.store_market_data(item)
                    all_data.append(item)
                logger.info(f"Collected {len(news_data)} industry news items")
            except Exception as e:
                logger.error(f"Error collecting industry news: {e}")
        
        logger.info(f"Total collected: {len(all_data)} new data points")
        return all_data
    
    def generate_report(self) -> str:
        """Generate weekly market research report"""
        try:
            recent_data = self.db_manager.get_recent_data(7)
            
            if not recent_data:
                logger.warning("No recent data found for report generation")
                return None
            
            logger.info(f"Generating report from {len(recent_data)} data points")
            report = self.report_generator.generate_weekly_report(recent_data)
            
            # Store report in database
            report_id = hashlib.md5(f"report_{datetime.now().isoformat()}".encode()).hexdigest()
            
            conn = sqlite3.connect(self.db_manager.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO reports (id, report_date, content, sources_cited, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                report_id, datetime.now().strftime('%Y-%m-%d'),
                report['content'], json.dumps(report['sources_cited']),
                datetime.now()
            ))
            conn.commit()
            conn.close()
            
            logger.info("Weekly report generated successfully")
            return report['content']
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return None
    
    def send_email_report(self, report_content: str):
        """Send report via email"""
        if not all([self.config.get('email_host'), self.config.get('email_user'), self.config.get('email_pass')]):
            logger.warning("Email configuration not complete. Skipping email send.")
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.config['email_user']
            msg['To'] = self.config.get('report_recipients', self.config['email_user'])
            msg['Subject'] = f"Weekly Market Research Report - {datetime.now().strftime('%Y-%m-%d')}"
            
            msg.attach(MIMEText(report_content, 'plain'))
            
            server = smtplib.SMTP(self.config['email_host'], self.config.get('email_port', 587))
            server.starttls()
            server.login(self.config['email_user'], self.config['email_pass'])
            server.send_message(msg)
            server.quit()
            
            logger.info("Report sent via email successfully")
            
        except Exception as e:
            logger.error(f"Error sending email report: {e}")
    
    async def run_collection_cycle(self):
        """Run a complete data collection cycle"""
        logger.info("Starting data collection cycle")
        await self.collect_data()
    
    def run_report_generation(self):
        """Run report generation"""
        logger.info("Generating weekly report")
        report = self.generate_report()
        
        if report:
            # Save to file
            report_path = f"reports/weekly_report_{datetime.now().strftime('%Y%m%d')}.md"
            Path("reports").mkdir(exist_ok=True)
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report)
            
            logger.info(f"Report saved to {report_path}")
            
            # Send via email if configured
            if self.config.get('send_email_reports', False):
                self.send_email_report(report)
    
    def start_monitoring(self):
        """Start the autonomous monitoring process"""
        logger.info("Starting market research agent...")
        
        # Run initial data collection
        logger.info("Running initial data collection...")
        asyncio.run(self.run_collection_cycle())
        
        # Generate initial report
        logger.info("Generating initial report...")
        self.run_report_generation()
        
        # Schedule data collection every 6 hours
        schedule.every(6).hours.do(lambda: asyncio.run(self.run_collection_cycle()))
        
        # Schedule weekly report generation (every Monday at 9 AM)
        schedule.every().monday.at("09:00").do(self.run_report_generation)
        
        logger.info("Market research agent started. Press Ctrl+C to stop.")
        logger.info("Scheduled tasks:")
        logger.info("- Data collection: Every 6 hours")
        logger.info("- Report generation: Every Monday at 9:00 AM")
        
        try:
            while True:
                logger.info("Checking for pending tasks...")
                schedule.run_pending()
                time.sleep(60)  # Check every minute
                
        except KeyboardInterrupt:
            logger.info("Market research agent stopped")

def create_sample_config():
    """Create a sample configuration file"""
    config = {
        "industry_keywords": [
            "artificial intelligence", 
            "machine learning", 
            "tech startup", 
            "your-industry-term"
        ],
        "news_api_key": "your-news-api-key-here (optional)",
        "email_host": "smtp.gmail.com",
        "email_port": 587,
        "email_user": "your-email@gmail.com",
        "email_pass": "your-app-password",
        "report_recipients": "recipient@company.com",
        "send_email_reports": False,
        "monitoring_sources": [
            {
                "url": "https://competitor1.com",
                "type": "website",
                "company": "Competitor1",
                "frequency": 24
            },
            {
                "url": "https://competitor2.com/news/rss",
                "type": "rss",
                "company": "Competitor2",
                "frequency": 12
            }
        ]
    }
    
    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)
    
    print("Sample config.json created!")
    print("\nNext steps:")
    print("1. Edit config.json with your industry keywords")
    print("2. Add competitor websites/RSS feeds")
    print("3. (Optional) Get a free News API key from https://newsapi.org")
    print("4. Run: python main.py")

def run_test_collection():
    """Run a test data collection to verify everything works"""
    print("Running test data collection...")
    
    agent = MarketResearchAgent()
    agent.setup_monitoring()
    
    # Run data collection
    asyncio.run(agent.run_collection_cycle())
    
    # Generate test report
    report = agent.generate_report()
    
    if report:
        print("\n" + "="*50)
        print("TEST REPORT GENERATED SUCCESSFULLY!")
        print("="*50)
        print(report[:500] + "..." if len(report) > 500 else report)
        print("\n" + "="*50)
        print(f"Full report saved to: reports/weekly_report_{datetime.now().strftime('%Y%m%d')}.md")
    else:
        print("No data collected yet. Try running again in a few hours.")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "setup":
            create_sample_config()
            sys.exit(0)
        elif sys.argv[1] == "test":
            run_test_collection()
            sys.exit(0)
        elif sys.argv[1] == "collect":
            # Manual data collection
            agent = MarketResearchAgent()
            agent.setup_monitoring()
            asyncio.run(agent.run_collection_cycle())
            print("Data collection completed!")
            sys.exit(0)
        elif sys.argv[1] == "report":
            # Manual report generation
            agent = MarketResearchAgent()
            agent.run_report_generation()
            print("Report generation completed!")
            sys.exit(0)
    
    # Initialize and start the agent
    agent = MarketResearchAgent()
    
    # Set up initial monitoring sources
    agent.setup_monitoring()
    
    # Start autonomous monitoring
    agent.start_monitoring()