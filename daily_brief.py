#!/usr/bin/env python3
"""
Jake's Daily News Review
Scrapes RSS feeds, summarises with Groq (Llama 3.3 70B), and sends via Resend.
"""

import feedparser
import trafilatura
import smtplib
import ssl
import time
import os
import re
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from groq import Groq

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────

CONFIG = {
    "groq_model":        "llama-3.3-70b-versatile",
    "articles_per_feed": 3,
    "recency_hours":     24,

    "email": {
        "sender":    os.environ["EMAIL_SENDER"],
        "password":  os.environ["BREVO_SMTP_KEY"],
        "recipient": os.environ["EMAIL_RECIPIENT"],
        "smtp_host": "smtp-relay.brevo.com",
        "smtp_port": 587,
    },
}

GROQ_CLIENT = Groq(api_key=os.environ["GROQ_API_KEY"])

# ─────────────────────────────────────────────
#  RSS FEEDS
# ─────────────────────────────────────────────

FEEDS = {
    "🌍 World News": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.reuters.com/rssFeed/worldNews",
        "https://rsshub.app/apnews/topics/apf-topnews",
        "https://www.aljazeera.com/xml/rss/all.xml",
        "https://rss.dw.com/rss/en-all",
    ],
    "💻 Tech / AI": [
        "https://feeds.feedburner.com/TechCrunch",
        "https://www.theverge.com/rss/index.xml",
        "https://hnrss.org/frontpage",
        "https://feeds.arstechnica.com/arstechnica/index",
        "https://www.technologyreview.com/feed/",
    ],
    "📈 Finance / Markets": [
        "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "https://www.economist.com/finance-and-economics/rss.xml",
    ],
    "🔬 Science": [
        "https://www.sciencedaily.com/rss/all.xml",
        "https://feeds.nature.com/nature/rss/current",
        "https://www.quantamagazine.org/feed/",
        "https://phys.org/rss-feed/",
    ],
}

# ─────────────────────────────────────────────
#  CORE LOGIC
# ─────────────────────────────────────────────

def is_recent(entry, hours):
    cutoff = datetime.now() - timedelta(hours=hours)
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6]) >= cutoff
            except Exception:
                pass
    return True


def fetch_articles(feeds, articles_per_feed, recency_hours):
    results = {}
    for category, urls in feeds.items():
        articles = []
        for url in urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    if not is_recent(entry, recency_hours):
                        continue
                    articles.append({
                        "title":   entry.get("title", "No title"),
                        "link":    entry.get("link", ""),
                        "summary": entry.get("summary", ""),
                        "source":  feed.feed.get("title", url),
                    })
            except Exception as e:
                print(f"  [WARN] Could not fetch {url}: {e}")
        seen, unique = set(), []
        for a in articles:
            if a["title"] not in seen:
                seen.add(a["title"])
                unique.append(a)
        results[category] = unique[:articles_per_feed * 2]
    return results


def scrape_full_text(url):
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            return trafilatura.extract(downloaded) or ""
    except Exception:
        pass
    return ""


def summarise_article(article):
    content = scrape_full_text(article["link"])
    if not content:
        content = article["summary"]
    if content:
        content = re.sub(r'<[^>]+>', '', content).strip()
    if not content:
        content = article["title"]

    prompt = (
        f"Summarise the following news article in exactly 2-3 concise sentences. "
        f"Be factual and neutral. Do not add opinions or padding.\n\n"
        f"Title: {article['title']}\n\n"
        f"Content:\n{content[:3000]}"
    )
    try:
        response = GROQ_CLIENT.chat.completions.create(
            model=CONFIG["groq_model"],
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[Summary unavailable: {e}]"


def build_brief(articles_by_category):
    brief = {}
    for category, articles in articles_by_category.items():
        print(f"\n  Summarising {category} ({len(articles)} articles)...")
        brief[category] = []
        for art in articles:
            print(f"    - {art['title'][:70]}")
            summary = summarise_article(art)
            brief[category].append({**art, "ai_summary": summary})
            time.sleep(0.3)
    return brief


# ─────────────────────────────────────────────
#  EMAIL RENDERING
# ─────────────────────────────────────────────

def render_html(brief):
    date_str = datetime.now().strftime("%A, %B %d %Y")
    sections_html = ""
    for category, articles in brief.items():
        articles_html = ""
        for art in articles:
            articles_html += (
                '<div class="article">'
                f'<a class="article-title" href="{art["link"]}" target="_blank">{art["title"]}</a>'
                f'<span class="source">{art["source"]}</span>'
                f'<p class="summary">{art["ai_summary"]}</p>'
                '</div>'
            )
        sections_html += (
            '<div class="section">'
            f'<h2>{category}</h2>'
            f'{articles_html}'
            '</div>'
        )

    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<style>'
        'body{font-family:Georgia,"Times New Roman",serif;background:#f5f0e8;color:#1a1a1a;margin:0;padding:0}'
        '.wrapper{max-width:680px;margin:0 auto;background:#fffdf7}'
        '.header{background:#1a1a2e;color:#e8d5b0;padding:32px 40px}'
        '.header h1{margin:0 0 4px;font-size:28px;letter-spacing:2px;text-transform:uppercase}'
        '.header .date{color:#a89070;font-size:13px;letter-spacing:1px}'
        '.content{padding:32px 40px}'
        '.section{margin-bottom:36px;border-bottom:1px solid #e0d8c8;padding-bottom:28px}'
        '.section:last-child{border-bottom:none}'
        'h2{font-size:16px;letter-spacing:1.5px;text-transform:uppercase;color:#8b6914;margin:0 0 20px;padding-bottom:8px;border-bottom:2px solid #e8d5b0}'
        '.article{margin-bottom:20px}'
        '.article-title{font-size:16px;font-weight:bold;color:#1a1a2e;text-decoration:none;line-height:1.3;display:block}'
        '.source{font-size:11px;color:#999;letter-spacing:0.5px;text-transform:uppercase;margin:3px 0 6px;display:block}'
        '.summary{font-size:14px;line-height:1.65;color:#444;margin:0}'
        '.footer{background:#1a1a2e;color:#666;padding:16px 40px;font-size:11px;text-align:center;letter-spacing:0.5px}'
        '</style></head><body>'
        '<div class="wrapper">'
        '<div class="header">'
        "<h1>Jake's Daily News Review</h1>"
        f'<div class="date">{date_str}</div>'
        '</div>'
        f'<div class="content">{sections_html}</div>'
        '<div class="footer">Generated by GitHub Actions &middot; Powered by Groq &middot; Delivered by Resend</div>'
        '</div></body></html>'
    )


# ─────────────────────────────────────────────
#  EMAIL SENDING
# ─────────────────────────────────────────────

def send_email(html, cfg):
    date_str = datetime.now().strftime("%b %d, %Y")
    recipients = [r.strip() for r in cfg["recipient"].split(",")]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Jake's Daily News Review - {date_str}"
    msg["From"]    = cfg["sender"]
    msg["To"]      = cfg["sender"]
    msg["BCC"]     = ", ".join(recipients)
    msg.attach(MIMEText(html, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(cfg["sender"], cfg["password"])
        server.sendmail(cfg["sender"], recipients, msg.as_string())
    print(f"\n  OK  Brief sent to {len(recipients)} recipient(s)")


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

def main():
    print("=" * 60)
    print(f"  Daily Brief  -  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    print("\n[1/4] Fetching articles from RSS feeds...")
    articles = fetch_articles(FEEDS, CONFIG["articles_per_feed"], CONFIG["recency_hours"])
    total = sum(len(v) for v in articles.values())
    print(f"      {total} articles collected across {len(FEEDS)} categories.")

    print("\n[2/4] Summarising with Groq...")
    brief = build_brief(articles)

    print("\n[3/4] Rendering HTML email...")
    html = render_html(brief)

    print("\n[4/4] Sending email...")
    send_email(html, CONFIG["email"])

    print("\nDone!\n")


if __name__ == "__main__":
    main()
