import asyncio
import os
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
import smtplib
import schedule
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import nltk
nltk.download('punkt_tab')  # Download punkt_tab
nltk.download('punkt')      # Ensure punkt is also available

# -------- SETTINGS (Change These) --------
NEWS_URL = "https://www.bbc.com/news"
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
# ------------------------------------------


def fetch_news_content(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        page_content = page.content()
        browser.close()
    return page_content


def extract_text(html):
    soup = BeautifulSoup(html, "html.parser")
    texts = soup.find_all(["p", "h1", "h2", "h3"])
    clean_text = " ".join([t.get_text(strip=True) for t in texts])
    return clean_text


def summarize_text(text, sentence_count=3):
    parser = PlaintextParser.from_string(text, Tokenizer("english"))
    summarizer = LsaSummarizer()
    summary = summarizer(parser.document, sentence_count)
    summarized_text = " ".join([str(sentence) for sentence in summary])
    return summarized_text


def send_email(subject, body):
    message = MIMEMultipart()
    message["From"] = EMAIL_FROM
    message["To"] = EMAIL_TO
    message["Subject"] = subject

    message.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, message.as_string())
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print("Failed to send email:", e)


def job():
    try:
        print("Fetching News...")
        html = fetch_news_content(NEWS_URL)

        print("Extracting Text...")
        text = extract_text(html)

        print("Summarizing...")
        summary = summarize_text(text)

        print("Sending Email...")
        send_email("Today's News Summary", summary)

    except Exception as error:
        print(f"Error occurred: {error}")


# Schedule the job daily at 9 AM
#schedule.every().day.at("09:00").do(job)
schedule.every(1).minutes.do(job)

print("Scheduler started. Waiting to run...")

while True:
    schedule.run_pending()
    time.sleep(60)


