import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DOCS_OUT_DIR = os.path.join(BASE_DIR, "docs_out")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DOCS_OUT_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "news.db")

SITES = [
    {"name": "TechCrunch", "rss": "https://techcrunch.com/feed/", "lang": "en"},
    {"name": "The Verge", "rss": "https://www.theverge.com/rss/index.xml", "lang": "en"},
    {"name": "Ars Technica", "rss": "https://feeds.arstechnica.com/arstechnica/index", "lang": "en"},
    {"name": "Wired", "rss": "https://www.wired.com/feed/rss", "lang": "en"},
    {"name": "Engadget", "rss": "https://www.engadget.com/rss.xml", "lang": "en"},
    {"name": "Habr", "rss": "https://habr.com/ru/rss/news/?fl=ru", "lang": "ru"},
    {"name": "3DNews", "rss": "https://www.3dnews.ru/news/rss/", "lang": "ru"},
    {"name": "Opennet", "rss": "https://www.opennet.ru/opennews/opennews_all.rss", "lang": "ru"},
    {"name": "iXBT", "rss": "https://www.ixbt.com/export/news.rss", "lang": "ru"},
    {"name": "N+1", "rss": "https://nplus1.ru/rss/news", "lang": "ru"},
]

LANGUAGES = {
    "en": {"label": "English", "hero_title": 'Tech news, <em>rewritten</em> fresh.',
           "hero_sub": " ",
           "empty": "Nothing published yet. Run collect, rewrite, then approve."},
    "ru": {"label": "Русский", "hero_title": 'Тех новости <em>по-новому</em>.',
           "hero_sub": " ",
           "empty": "Пока ничего не опубликовано. Запустите collect, затем rewrite и approve."},
}

AI_PROVIDER = os.getenv("AI_PROVIDER", "deepseek").lower()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct")

REWRITE_STYLE = os.getenv("REWRITE_STYLE", "casual")
ARTICLES_PER_SITE = int(os.getenv("ARTICLES_PER_SITE", "5"))
REWRITE_LIMIT_PER_RUN = int(os.getenv("REWRITE_LIMIT_PER_RUN", "5"))
COLLECT_INTERVAL_MINUTES = int(os.getenv("COLLECT_INTERVAL_MINUTES", "120"))
REWRITE_INTERVAL_MINUTES = int(os.getenv("REWRITE_INTERVAL_MINUTES", "30"))

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
FLASK_SECRET = os.getenv("FLASK_SECRET", "change-this-secret")

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "5000"))

STATUSES = ["collected", "processing", "pending_approval", "published", "rejected"]
