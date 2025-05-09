import asyncio
import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
import smtplib
import schedule
import time
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import nltk

# Download NLTK data
nltk.download('punkt_tab')
nltk.download('punkt')

# Configure logging
logging.basicConfig(
    filename='news_summary.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()

# -------- SETTINGS --------
NEWS_URL = "https://www.bbc.com/news"
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
# -------------------------

# Validate environment variables
if not all([EMAIL_FROM, EMAIL_PASSWORD, EMAIL_TO]):
    logging.error("Missing environment variables: EMAIL_FROM, EMAIL_PASSWORD, or EMAIL_TO")
    raise ValueError("Missing required environment variables")

def fetch_news_content(url):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            page.goto(url, timeout=120000)
            page.wait_for_selector("article, .gs-c-promo-body", timeout=20000)
            page_content = page.content()
            browser.close()
        logging.info("Successfully fetched content from %s", url)
        return page_content
    except PlaywrightTimeoutError:
        logging.error("Timeout while fetching %s", url)
        raise
    except Exception as e:
        logging.error("Error fetching content: %s", e)
        raise

def extract_text(html):
    soup = BeautifulSoup(html, "html.parser")
    # More specific selectors for BBC News articles
    articles = soup.select("article p, .gs-c-promo-body p:not(.gs-c-promo-summary)")
    clean_text = []
    for t in articles:
        text = t.get_text(strip=True)
        # Skip boilerplate or short irrelevant text
        if text and len(text) > 20 and "read more" not in text.lower():
            clean_text.append(text)
    clean_text = " ".join(clean_text)
    if not clean_text:
        logging.warning("No text extracted from HTML")
    logging.info("Extracted text length: %d characters", len(clean_text))
    return clean_text

def summarize_text(text, sentence_count=5):
    if not text:
        return "No content available to summarize."
    parser = PlaintextParser.from_string(text, Tokenizer("english"))
    summarizer = LsaSummarizer()
    summary = summarizer(parser.document, sentence_count)
    summarized_text = "\n".join([f"- {str(sentence)}" for sentence in summary])
    logging.info("Generated summary with %d sentences", sentence_count)
    return summarized_text

def send_email(subject, body):
    message = MIMEMultipart()
    message["From"] = EMAIL_FROM
    message["To"] = EMAIL_TO
    message["Subject"] = f"{subject} - {time.strftime('%Y-%m-%d')}"

    # Use HTML for better formatting
    html_body = f"""
    <html>
        <body>
            <h2>Daily News Summary</h2>
            <p>{body.replace('\n', '<br>')}</p>
        </body>
    </html>
    """
    message.attach(MIMEText(html_body, "html"))

    for attempt in range(3):
        try:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, message.as_string())
            server.quit()
            logging.info("Email sent successfully to %s", EMAIL_TO)
            return
        except Exception as e:
            logging.error("Failed to send email (attempt %d): %s", attempt + 1, e)
            time.sleep(2)
    logging.error("Failed to send email after 3 attempts")

def job():
    try:
        logging.info("Starting news summary job")
        html = fetch_news_content(NEWS_URL)
        text = extract_text(html)
        summary = summarize_text(text, sentence_count=5)
        logging.info("Summary:\n%s", summary)
        send_email("Daily News Summary", summary)
    except Exception as e:
        logging.error("Job failed: %s", e)

def main():
    logging.info("EMAIL_FROM: %s, EMAIL_TO: %s", EMAIL_FROM, EMAIL_TO)

    # Schedule every minute for testing
    #schedule.every(1).minutes.do(job)
    
    #For production: 
    schedule.every().day.at("09:00").do(job)

    logging.info("Scheduler started")

    if os.getenv("RUN_NOW") == "true":
        logging.info("Running job manually")
        job()

    try:
        while True:
            logging.info("Checking schedule...")
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logging.info("Scheduler stopped by user")
        print("Scheduler stopped.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error("Script failed: %s", e)
        print(f"Script failed: {e}")

