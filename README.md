# TechPulse — Local News Collector & Publisher

Collects tech news from 5 sites → AI rewrites them in a casual style (DeepSeek / Qwen) → you approve via CLI or dashboard → approved articles go live on the local website.

Designed for **2-core Windows + 16 GB RAM**: SQLite, Flask single-process, sequential scraping, cloud AI (zero GPU load). Optional fully-offline mode with Ollama.

## Architecture

```
RSS/HTML ──▶ Scraper ──▶ SQLite (status: collected)
                              │
                    AI Rewriter (deepseek/qwen/ollama)
                              │
                     status: pending_approval
                              │
              ┌── CLI approval ──┐
              │                  │
      python cli.py approve    /admin dashboard
              │                  │
              ▔▔▔▔▔▔▔ status: published ▔▔▔▔▔
                              │
                   Flask site @ localhost:5000
```

## Step-by-step setup

### 1. Install Python
Install Python 3.10+ from python.org. Check "Add to PATH" during install.

### 2. Create environment & install deps
```bat
cd news_collector
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### 3. Get a free/cheap AI key (pick ONE)

**Fully local, zero API (recommended for your machine):**
1. Install Ollama: https://ollama.com/download (Windows installer)
2. Pull a small Qwen model sized for 2 cores:
   ```bat
   ollama pull qwen2.5:3b-instruct        ~2 GB RAM, best quality/speed balance
   ollama pull qwen2.5:1.5b-instruct      ~1 GB RAM, faster, lower quality
   ```
3. In `.env` set `AI_PROVIDER=ollama` — done, no internet AI calls ever.
4. Verify everything with `python cli.py doctor`.

Speed expectation on 2 CPU cores: roughly **1–3 minutes per article**. The scheduler rewrites the queue in the background so it stays fully automatic — set `REWRITE_LIMIT_PER_RUN=3` in `.env` to keep each run light.

| Provider | Cost | Where to get key |
|----------|------|------------------|
| **Ollama (local)** | Free forever, offline | No key needed |
| **Qwen cloud** | Free quota (~1M tokens new accounts) | https://modelstudio.console.alibabacloud.com → API-KEY |
| **DeepSeek cloud** | Not free but extremely cheap (~$0.01 per ~100 rewrites) | https://platform.deepseek.com |

Edit `.env`:
```ini
AI_PROVIDER=qwen            # deepseek | qwen | ollama
DASHSCOPE_API_KEY=sk-...    # if qwen
DEEPSEEK_API_KEY=sk-...     # if deepseek
ADMIN_PASSWORD=your-password
FLASK_SECRET=some-random-string
```

For Ollama set `AI_PROVIDER=ollama` — no key needed. Note: on 2 CPU cores rewriting takes ~1-3 min/article.

### 4. Initialize and do the first run
```bat
python cli.py init        create the database
python cli.py collect     scrape all 5 sites now
python cli.py rewrite     AI-rewrite collected articles (default 5 per run)
python cli.py pending     list articles waiting for approval
python cli.py show 3      read rewritten article #3 in terminal
python cli.py export      save pending docs as markdown files in docs_out\
```

### 5. Approve via command line
```bat
python cli.py approve 3       approve one article by id
python cli.py approve all     approve everything pending
python cli.py reject 5        discard article #5
python cli.py stats           counts by status
```

### 6. Run the website (with auto-scheduler)
```bat
python app.py
```
- Public site: http://127.0.0.1:5000
- Admin dashboard: http://127.0.0.1:5000/admin (password from `.env`)
- Auto-collects every 120 min and auto-rewrites every 30 min (configurable in `.env`).

On the dashboard you can also trigger Collect/Rewrite manually and Approve/Reject with buttons.

### 7. Keep it running (optional autostart)
Open Task Scheduler → Create Basic Task → Trigger "At startup" → Action "Start a program":
- Program: `C:\...\news_collector\venv\Scripts\python.exe`
- Arguments: `app.py`
- Start in: `C:\...\news_collector`

## Daily workflow

```
collect  →  rewrite  →  review (show/export)  →  approve  →  live on website
```
Everything else is automated by the scheduler inside `app.py`.

## Resource notes (2 cores / 16 GB)
- Flask runs single process with threads — well under 100 MB RAM.
- Scraping is sequential with delays to avoid hammering sites/CPU.
- All heavy AI work happens on DeepSeek/Qwen servers (free tiers), not your machine.
- SQLite needs zero configuration and handles this volume effortlessly.

## Changing sources or style
- Sites: edit `SITES` in `config.py` (any RSS feed works).
- Style: set `REWRITE_STYLE` = `casual`, `professional`, or `explainer` in `.env`.

## Legal note
Rewrite for commentary/summary purposes and always link back to the original source (the site does automatically). Respect each source's terms of service.
"# TNV" 
"# TNV" 
