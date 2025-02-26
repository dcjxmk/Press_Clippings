from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import json
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
import logging
from readability import Document
import newspaper
from bs4 import BeautifulSoup
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.platypus.frames import Frame
from reportlab.platypus.doctemplate import PageTemplate
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
import tempfile
from langdetect import detect
import trafilatura
from docx import Document as DocxDocument
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import docx
from docx.oxml import parse_xml
from reportlab.lib.enums import TA_CENTER, TA_LEFT

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clippings.db'
db = SQLAlchemy(app)
CORS(app)

class Clipping(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    headline = db.Column(db.String(200), nullable=False)
    source = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    url = db.Column(db.String(500))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    order = db.Column(db.Integer)

    def to_dict(self):
        return {
            'id': self.id,
            'headline': self.headline,
            'source': self.source,
            'category': self.category,
            'content': self.content,
            'url': self.url,
            'date': self.date.strftime('%Y-%m-%d'),
            'order': self.order
        }

with app.app_context():
    db.create_all()

def get_webdriver():
    """Try different browsers in order of preference"""
    browsers = [
        # Chrome
        {
            'try': lambda: webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()),
                options=webdriver.ChromeOptions().add_argument('--headless')
            ),
            'name': 'Chrome'
        },
        # Edge
        {
            'try': lambda: webdriver.Edge(
                service=EdgeService(EdgeChromiumDriverManager().install()),
                options=webdriver.EdgeOptions().add_argument('--headless')
            ),
            'name': 'Edge'
        },
        # Firefox
        {
            'try': lambda: webdriver.Firefox(
                service=Service(GeckoDriverManager().install()),
                options=Options().add_argument('--headless')
            ),
            'name': 'Firefox'
        }
    ]
    
    last_error = None
    for browser in browsers:
        try:
            driver = browser['try']()
            logging.info(f"Successfully initialized {browser['name']} webdriver")
            return driver
        except Exception as e:
            last_error = e
            logging.warning(f"Failed to initialize {browser['name']} webdriver: {e}")
            continue
    
    raise RuntimeError(f"Could not initialize any webdriver. Last error: {last_error}")

def scrape_url(url):
    # Try trafilatura first (good for news sites)
    downloaded = trafilatura.fetch_url(url)
    if downloaded:
        article_text = trafilatura.extract(downloaded, include_comments=False, 
                                         include_tables=False, 
                                         favor_precision=True)
        if article_text:
            # Split into paragraphs and clean
            paragraphs = [p.strip() for p in article_text.split('\n\n') if p.strip()]
            if len(paragraphs) >= 2:
                content = '\n\n'.join(paragraphs[:2])
                # Try to get a better title from the metadata
                metadata = trafilatura.extract_metadata(downloaded)
                title = metadata.get('title', paragraphs[0]) if metadata else paragraphs[0]
                
                # Detect language to handle German content
                try:
                    lang = detect(content)
                    if lang == 'de':
                        # German content - no additional processing needed
                        pass
                except:
                    pass
                return {
                    'headline': title,
                    'source': url.split('/')[2],
                    'content': content,
                    'url': url
                }
    
    # If trafilatura fails, try newspaper3k
    try:
        article = newspaper.Article(url)
        article.download()
        article.parse()
        
        if article.text:
            paragraphs = [p.strip() for p in article.text.split('\n\n') if p.strip()]
            content = '\n\n'.join(paragraphs[:2])
            return {
                'headline': article.title,
                'source': url.split('/')[2],
                'content': content,
                'url': url
            }
    except Exception as e:
        logging.error(f"newspaper3k extraction failed: {str(e)}")
    
    # Only use selenium as a last resort
    driver = get_webdriver()
    try:
        driver.get(url)
        
        # Special handling for news24.co.za
        if 'news24.co.za' in url:
            try:
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                
                # Set a longer wait time for news24
                wait = WebDriverWait(driver, 10)
                
                # Try to get article content with multiple fallback selectors
                content_selectors = [
                    '.article__body p',
                    '.article__text p',
                    '[itemprop="articleBody"] p',
                    '#article-body p'
                ]
                
                paragraphs = []
                for selector in content_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            paragraphs = [p.text.strip() for p in elements if p.text.strip()]
                            if len(paragraphs) >= 2:
                                break
                    except:
                        continue
                
                if paragraphs:
                    # Try different headline selectors
                    headline_selectors = ['.article__title', 'h1', '[itemprop="headline"]']
                    headline = None
                    for selector in headline_selectors:
                        try:
                            headline_elem = driver.find_element(By.CSS_SELECTOR, selector)
                            if headline_elem:
                                headline = headline_elem.text.strip()
                                break
                        except:
                            continue
                    
                    if not headline:
                        headline = paragraphs[0]
                    
                    return {
                        'headline': headline,
                        'source': 'news24.co.za',
                        'content': '\n\n'.join(paragraphs[:2]),
                        'url': url
                    }
            except Exception as e:
                logging.error(f"Error scraping news24: {str(e)}")
        
        # Generic selenium scraping as last resort
        doc = Document(driver.page_source)
        soup = BeautifulSoup(doc.summary(), 'html.parser')
        paragraphs = soup.find_all('p')
        
        if len(paragraphs) < 2:
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            for container in ['article', '[role="article"]', 'main', '[role="main"]']:
                article_content = soup.select(container)
                if article_content:
                    paragraphs = article_content[0].find_all('p')
                    if len(paragraphs) >= 2:
                        break
        
        valid_paragraphs = []
        for p in paragraphs:
            text = p.get_text().strip()
            if (len(text) > 50 and 
                'advertisement' not in text.lower() and 
                'subscribe' not in text.lower() and 
                'cookie' not in text.lower()):
                valid_paragraphs.append(text)
            if len(valid_paragraphs) == 2:
                break
        
        if valid_paragraphs:
            title = soup.title.string if soup.title else valid_paragraphs[0]
            return {
                'headline': title,
                'source': url.split('/')[2],
                'content': '\n\n'.join(valid_paragraphs),
                'url': url
            }
        
        raise Exception("Could not extract content from page")
        
    finally:
        driver.quit()

def generate_pdf(clippings):
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    doc = SimpleDocTemplate(
        temp_file.name,
        pagesize=A4,
        leftMargin=2*cm,
        rightMargin=2*cm,
        topMargin=2.5*cm,
        bottomMargin=2.5*cm
    )
    
    styles = getSampleStyleSheet()
    
    # Main title: 16pt, bold, underlined
    current_date = datetime.now()
    day_name = current_date.strftime('%A')
    date_str = current_date.strftime('%d %B %Y')
    title_text = f"Embassy Press Clippings – {day_name}, {date_str}"
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=16,
        leading=20,
        alignment=1,  # Center alignment
        textColor=colors.black,
        underline=True
    )
    
    # Category style: 14pt, bold, underline
    category_style = ParagraphStyle(
        'CategoryStyle',
        parent=styles['Heading1'],
        fontSize=14,
        leading=18,
        textColor=colors.black,
        underline=True,
        spaceAfter=12
    )
    
    # Article headline style: 10.5pt, bold
    headline_style = ParagraphStyle(
        'HeadlineStyle',
        parent=styles['Normal'],
        fontSize=10.5,
        leading=13,
        bold=True
    )
    
    # Article content style: 10.5pt
    content_style = ParagraphStyle(
        'ContentStyle',
        parent=styles['Normal'],
        fontSize=10.5,
        leading=13
    )
    
    # Source style: blue for URL
    source_style = ParagraphStyle(
        'SourceStyle',
        parent=styles['Normal'],
        fontSize=10.5,
        leading=13,
        textColor=colors.blue,
        spaceAfter=12
    )
    
    story = []
    
    # Add title
    story.append(Paragraph(f"<b><u>{title_text}</u></b>", title_style))
    story.append(Spacer(1, 20))
    
    # Fixed categories in specific order
    fixed_categories = [
        "Foreign Politics",
        "Domestic Politics",
        "Economy, Energy, Climate & Agriculture",
        "Verschiedenes",
        "Cartoon"
    ]
    
    # Group clippings by category
    category_groups = {cat: [] for cat in fixed_categories}
    for clipping in clippings:
        # Map user categories to fixed categories (case-insensitive)
        user_cat = clipping.category.strip()
        # Try to find matching category
        matched = False
        for fixed_cat in fixed_categories:
            if user_cat.lower() == fixed_cat.lower() or user_cat.lower() in fixed_cat.lower():
                category_groups[fixed_cat].append(clipping)
                matched = True
                break
        # If no match found, put in Verschiedenes
        if not matched:
            category_groups["Verschiedenes"].append(clipping)

    # Process each category in order
    for category in fixed_categories:
        articles = category_groups.get(category, [])
        
        # Only show categories with articles or Cartoon category
        if articles or category == "Cartoon":
            # Add category header (14pt, bold, underlined)
            story.append(Paragraph(f"<b><u>{category}</u></b>", category_style))
            
            if articles:
                for clipping in sorted(articles, key=lambda x: x.order):
                    # Article headline (10.5pt, bold)
                    story.append(Paragraph(f"<b>{clipping.headline}</b>", headline_style))
                    
                    # Article content (10.5pt)
                    story.append(Paragraph(clipping.content, content_style))
                    
                    # Source and date (blue for source if URL exists)
                    date_str = clipping.date.strftime('%d/%m/%Y')
                    if clipping.url:
                        source_text = f'<link href="{clipping.url}"><font color="blue">{clipping.source}</font></link>'
                    else:
                        source_text = clipping.source
                    story.append(Paragraph(f"{source_text} | {date_str}", source_style))
                    
                    story.append(Spacer(1, 12))  # Space between articles
            
            story.append(Spacer(1, 12))  # Space after category
    
    try:
        doc.build(story)
    except Exception as e:
        logging.error(f"Error generating PDF: {str(e)}")
        raise
    
    return temp_file.name

def generate_docx(clippings):
    doc = DocxDocument()
    
    # Title formatting (16pt, bold, underlined)
    current_date = datetime.now()
    day_name = current_date.strftime('%A')
    date_str = current_date.strftime('%d %B %Y')
    title = doc.add_paragraph()
    title_run = title.add_run(f"Embassy Press Clippings – {day_name}, {date_str}")
    title_run.bold = True
    title_run.font.size = Pt(16)
    title_run.font.underline = True
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_paragraph()  # Add space after title
    
    # Fixed categories in specific order
    fixed_categories = [
        "Foreign Politics",
        "Domestic Politics",
        "Economy, Energy, Climate & Agriculture",
        "Verschiedenes",
        "Cartoon"
    ]
    
    # Group clippings by category
    category_groups = {cat: [] for cat in fixed_categories}
    for clipping in clippings:
        # Map user categories to fixed categories (case-insensitive)
        user_cat = clipping.category.strip()
        # Try to find matching category
        matched = False
        for fixed_cat in fixed_categories:
            if user_cat.lower() == fixed_cat.lower() or user_cat.lower() in fixed_cat.lower():
                category_groups[fixed_cat].append(clipping)
                matched = True
                break
        # If no match found, put in Verschiedenes
        if not matched:
            category_groups["Verschiedenes"].append(clipping)

    # Process each category
    for category in fixed_categories:
        articles = category_groups.get(category, [])
        
        # Only show categories with articles or Cartoon category
        if articles or category == "Cartoon":
            # Category header (14pt, bold, underlined)
            cat_heading = doc.add_paragraph()
            cat_run = cat_heading.add_run(category)
            cat_run.bold = True
            cat_run.font.size = Pt(14)
            cat_run.font.underline = True
            
            doc.add_paragraph()  # Space after category header
            
            if articles:
                for clipping in sorted(articles, key=lambda x: x.order):
                    # Article headline (10.5pt, bold)
                    headline = doc.add_paragraph()
                    headline_run = headline.add_run(clipping.headline)
                    headline_run.bold = True
                    headline_run.font.size = Pt(10.5)
                    
                    # Article content (10.5pt)
                    content = doc.add_paragraph()
                    content_run = content.add_run(clipping.content)
                    content_run.font.size = Pt(10.5)
                    
                    # Source and date line
                    source_para = doc.add_paragraph()
                    date_str = clipping.date.strftime('%d/%m/%Y')
                    
                    # Add source as hyperlink if URL exists
                    if clipping.url:
                        # Create hyperlink with blue color
                        rel_id = doc.part.relate_to(clipping.url, docx.opc.constants.RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
                        hyperlink = docx.oxml.shared.OxmlElement('w:hyperlink')
                        hyperlink.set(docx.oxml.shared.qn('r:id'), rel_id)
                        
                        # Create run for hyperlink
                        run = docx.oxml.shared.OxmlElement('w:r')
                        run_props = docx.oxml.shared.OxmlElement('w:rPr')
                        
                        # Set blue color
                        color = docx.oxml.shared.OxmlElement('w:color')
                        color.set(docx.oxml.shared.qn('w:val'), '0000FF')
                        run_props.append(color)
                        
                        # Set underline
                        underline = docx.oxml.shared.OxmlElement('w:u')
                        underline.set(docx.oxml.shared.qn('w:val'), 'single')
                        run_props.append(underline)
                        
                        run.append(run_props)
                        text = docx.oxml.shared.OxmlElement('w:t')
                        text.text = clipping.source
                        run.append(text)
                        hyperlink.append(run)
                        source_para._p.append(hyperlink)
                    else:
                        source_para.add_run(clipping.source)
                    
                    # Add date
                    source_para.add_run(f" | {date_str}")
                    
                    doc.add_paragraph()  # Space between articles
            
            doc.add_paragraph()  # Space after category
    
    # Save to temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.docx')
    try:
        doc.save(temp_file.name)
    except Exception as e:
        logging.error(f"Error generating Word document: {str(e)}")
        raise
    
    return temp_file.name

def purge_old_clippings():
    with app.app_context():
        cutoff_date = datetime.utcnow() - timedelta(hours=24)
        Clipping.query.filter(Clipping.date < cutoff_date).delete()
        db.session.commit()

# Initialize the scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=purge_old_clippings, trigger="interval", hours=1)
scheduler.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scrape', methods=['POST'])
def scrape():
    url = request.json.get('url')
    try:
        result = scrape_url(url)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/clippings', methods=['GET', 'POST'])
def handle_clippings():
    if request.method == 'POST':
        data = request.json
        clipping = Clipping(
            headline=data['headline'],
            source=data['source'],
            category=data['category'],
            content=data['content'],
            url=data.get('url'),
            order=len(Clipping.query.all())
        )
        db.session.add(clipping)
        db.session.commit()
        return jsonify(clipping.to_dict())
    
    clippings = Clipping.query.order_by(Clipping.order).all()
    return jsonify([c.to_dict() for c in clippings])

@app.route('/api/clippings/reorder', methods=['POST'])
def reorder_clippings():
    new_order = request.json
    for item in new_order:
        clipping = Clipping.query.get(item['id'])
        if clipping:
            clipping.order = item['order']
    db.session.commit()
    return '', 204

@app.route('/api/clippings/<int:clipping_id>', methods=['PUT', 'DELETE'])
def handle_clipping(clipping_id):
    clipping = Clipping.query.get_or_404(clipping_id)
    
    if request.method == 'DELETE':
        db.session.delete(clipping)
        db.session.commit()
        return '', 204
    elif request.method == 'PUT':
        data = request.json
        for key, value in data.items():
            setattr(clipping, key, value)
        db.session.commit()
        return jsonify(clipping.to_dict())

@app.route('/api/export/pdf')
def export_pdf():
    clippings = Clipping.query.order_by(Clipping.order).all()
    pdf_path = generate_pdf(clippings)
    
    return send_file(
        pdf_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='press_clippings.pdf'
    )

@app.route('/api/export/docx')
def export_docx():
    clippings = Clipping.query.order_by(Clipping.order).all()
    docx_path = generate_docx(clippings)
    
    return send_file(
        docx_path,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        as_attachment=True,
        download_name='press_clippings.docx'
    )

@app.route('/api/clippings/delete-all', methods=['DELETE'])
def delete_all_clippings():
    try:
        Clipping.query.delete()
        db.session.commit()
        return '', 204
    except Exception as e:
        logging.error(f"Error deleting all clippings: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)