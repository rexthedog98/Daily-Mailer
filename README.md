# Daily Mailer

An automated daily news briefing. A GitHub Actions workflow runs every morning, pulls fresh articles from RSS feeds across World News, Tech/AI, Finance, and Science, summarizes each with Groq (Llama 3.3 70B), and emails a formatted HTML digest via Brevo SMTP.

## How it works

1. **Fetch** — pulls entries from RSS feeds in each category (`daily_brief.py`), keeping only articles published in the last 24 hours and de-duplicating by title.
2. **Scrape & summarize** — for each article, `trafilatura` extracts the full article text from its link (falling back to the RSS summary if scraping fails), then Groq's `llama-3.3-70b-versatile` condenses it into a neutral 2–3 sentence summary.
3. **Render** — builds a styled HTML email grouping articles by category.
4. **Send** — delivers the email over SMTP via Brevo, BCC'ing all configured recipients.

The whole pipeline runs on a schedule via GitHub Actions (`.github/workflows/daily_brief.yml`), currently at 11:00 UTC daily, and can also be triggered manually from the Actions tab.

## Feed categories

- 🌍 World News (BBC, Reuters, AP, Al Jazeera, DW)
- 💻 Tech / AI (TechCrunch, The Verge, Hacker News, Ars Technica, MIT Tech Review)
- 📈 Finance / Markets (Dow Jones, WSJ, The Economist)
- 🔬 Science (ScienceDaily, Nature, Quanta, Phys.org)

## Setup

### Requirements

```bash
pip install -r requirements.txt
```

### Environment variables / secrets

The script expects the following to be set (as GitHub Actions secrets for CI, or environment variables for local runs):

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | API key for Groq (article summarization) |
| `BREVO_SMTP_LOGIN` | Brevo SMTP login (e.g. `xxxxx001@smtp-brevo.com`) |
| `BREVO_SMTP_KEY` | Brevo SMTP key/password |
| `EMAIL_SENDER` | Sender email address |
| `EMAIL_RECIPIENT` | Comma-separated list of recipient email addresses |

### Running locally

```bash
export GROQ_API_KEY=...
export BREVO_SMTP_LOGIN=...
export BREVO_SMTP_KEY=...
export EMAIL_SENDER=...
export EMAIL_RECIPIENT=...
python daily_brief.py
```

### Running via GitHub Actions

Set the same five values as repository secrets (Settings → Secrets and variables → Actions), then the `Daily Brief` workflow will run automatically on its cron schedule, or can be triggered manually via `workflow_dispatch`.

## Configuration

Feed lists, articles-per-feed count, recency window, and the Groq model can all be adjusted in the `FEEDS` and `CONFIG` dictionaries at the top of `daily_brief.py`.
