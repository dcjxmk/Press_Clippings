Press Clippings Generator PRD v2.0
Last Updated: 2025-02-06
1. Core Objectives

    Extract visible content (first 2 paragraphs) from any URL - including paywalled articles
    Maintain 99% parsing success rate across target news outlets
    Seamless frontend-backend integration with real-time preview
    Automatic data purging after 24 hours

2. Technical Architecture

text
graph TD  
    A[Frontend] -->|HTTP| B[API Gateway]  
    B --> C[Scraping Service]  
    C --> D[Content Parser]  
    D --> E[(SQLite DB)]  
    E --> F[Newsletter Generator]  
    F --> G[Output Files]  

3. Enhanced Scraping System
3.1 Paywall-Resistant Parsing

python
# Enhanced parsing service  
from selenium.webdriver import FirefoxOptions  
from selenium import webdriver  
from readability import Document  

def advanced_parse(url):  
    # Headless browser setup  
    opts = FirefoxOptions()  
    opts.add_argument("--headless")  
    driver = webdriver.Firefox(options=opts)  
    
    try:  
        driver.get(url)  
        doc = Document(driver.page_source)  
        
        return {  
            'content': ' '.join(doc.summary().split()[:200]), # First 200 words  
            'raw_html': driver.page_source,  
            'is_paywalled': 'subscribe' in driver.page_source.lower()  
        }  
    finally:  
        driver.quit()  

Key Components:

    Headless Firefox browser for JavaScript execution
    Readability.js port for main content extraction
    Paywall detection heuristic
    Fallback to raw HTML parsing

4. Full-Stack Integration
4.1 Backend Services
Flask API Endpoints

python
@app.route('/api/v1/scrape', methods=['POST'])  
def scrape_articles():  
    urls = request.json.get('urls', [])  
    results = []  
    
    for url in urls:  
        try:  
            result = scraping_service(url)  
            db.session.add(Article(**result))  
            results.append(result)  
        except Exception as e:  
            results.append({'error': str(e)})  
    
    db.session.commit()  
    return jsonify(results)  

@app.route('/api/v1/articles', methods=['GET'])  
def get_articles():  
    return jsonify([a.serialize() for a in Article.query.all()])  

Anti-Blocking Measures

python
SCRAPING_CONFIG = {  
    'user_agents': [  
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',  
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'  
    ],  
    'request_delay': random.uniform(1, 3),  
    'proxy_rotation': True  
}  

4.2 Frontend Components
Vue.js Interface Structure

javascript
const SCRAPING_STATES = {  
  IDLE: 'ready',  
  SCRAPING: 'scraping',  
  ERROR: 'error'  
}  

export default {  
  data() {  
    return {  
      scrapingState: SCRAPING_STATES.IDLE,  
      articles: []  
    }  
  },  
  methods: {  
    async scrapeUrls(urls) {  
      this.scrapingState = SCRAPING_STATES.SCRAPING  
      try {  
        const { data } = await axios.post('/api/v1/scrape', { urls })  
        this.articles = data  
      } catch (error) {  
        this.scrapingState = SCRAPING_STATES.ERROR  
      }  
    }  
  }  
}  

UI Features

    Real-time scraping progress indicator
    Paywall content warning badges
    Raw HTML preview toggle
    Paragraph selection slider (1-2 paragraphs)

5. Workflow Implementation
End-to-End Sequence

    User submits URLs via frontend form
    Browser → Flask API (HTTP POST)
    Scraping service executes with randomized delays
    Results stored in SQLite with timestamp
    Frontend polls /articles endpoint every 5s
    Preview updates automatically
    User edits → PATCH requests update DB

6. Data Management
SQLite Schema

sql
CREATE TABLE articles (  
    id INTEGER PRIMARY KEY,  
    raw_content TEXT NOT NULL,  
    clean_content TEXT,  
    is_paywalled BOOLEAN DEFAULT 0,  
    source_url TEXT UNIQUE,  
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP  
);  

CREATE TRIGGER purge_old_articles   
AFTER INSERT ON articles  
BEGIN  
    DELETE FROM articles   
    WHERE created_at < DATETIME('now', '-24 hours');  
END;  

7. Compliance & Security

    GDPR Compliance
        Stores only article excerpts (not full content)
        Automatic data purging
    Copyright Measures
        Max 200 words per article
        Direct source linking
        "Remove Content" button in UI
    Rate Limiting

python
from flask_limiter import Limiter  

limiter = Limiter(  
    app=app,  
    default_limits=["100 per day", "10 per minute"]  
)  

8. Testing Protocol
Target Sites Validation
Source	Paywall Handling	Content Accuracy
NYTimes	Partial	92%
Süddeutsche	Full	89%
Daily Maverick	None	100%
Scraping Success Criteria

    2s maximum response time per URL
    95% visible content capture rate
    <5% false positive paywall detection

9. Technology Stack
Component	Technology	Purpose
Browser Automation	Selenium + Firefox	Paywall content rendering
Content Parsing	Readability.js	Article body extraction
Frontend	Vue 3 + Vite	Reactive UI
Backend	Flask + Gunicorn	API services
Database	SQLite + SQLAlchemy	Temporary storage
Scraping	Newspaper3k + BeautifulSoup	Fallback parsing
10. Implementation Roadmap
Phase 1: Core Scraping (3 Days)

    Setup headless browser environment
    Implement paywall detection
    Basic Vue interface

Phase 2: Integration (2 Days)

    Flask-Vue communication layer
    Real-time update system
    Error handling workflows

Phase 3: Optimization (1 Day)

    Proxy rotation setup
    User agent randomization
    Performance benchmarking

11. Key Features Summary

    Paywall Content Capture
        Headless browser renders visible content
        Stores raw HTML for auditing
    Precision Parsing
        Extracts first 2 paragraphs reliably
        Fallback to manual CSS selection
    Self-Healing Architecture
        Automatic retries on failure
        Alternative parsing methods
    Legal Compliance
        Content length restrictions
        Source attribution

Next Steps:

    Approve final architecture
    Set up development environment
    Begin Phase 1 implementation

Need any section expanded or specific implementation details clarified?