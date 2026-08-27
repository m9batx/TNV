import sqlite3
from datetime import datetime, timezone
from config import DB_PATH


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            title TEXT,
            original_text TEXT,
            rewritten_title TEXT,
            rewritten_text TEXT,
            provider TEXT,
            image_url TEXT,
            status TEXT DEFAULT 'collected',
            lang TEXT DEFAULT 'en',
            published_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_status ON articles(status);
    """)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(articles)").fetchall()]
    if "lang" not in cols:
        conn.execute("ALTER TABLE articles ADD COLUMN lang TEXT DEFAULT 'en'")
        conn.commit()
    if "progress" not in cols:
        conn.execute("ALTER TABLE articles ADD COLUMN progress INTEGER DEFAULT 0")
        conn.commit()
    conn.close()


def insert_article(source, url, title, text, image_url=None, lang="en"):
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO articles (source, url, title, original_text, image_url, lang) VALUES (?,?,?,?,?,?)",
            (source, url, title, text, image_url, lang),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_articles_by_status(status, limit=200, lang=None):
    conn = get_db()
    order = "ORDER BY COALESCE(published_at, created_at) DESC"
    if lang:
        rows = conn.execute(
            f"SELECT * FROM articles WHERE status=? AND lang=? {order} LIMIT ?",
            (status, lang, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT * FROM articles WHERE status=? {order} LIMIT ?",
            (status, limit),
        ).fetchall()
    conn.close()
    return rows


def get_article(aid):
    conn = get_db()
    row = conn.execute("SELECT * FROM articles WHERE id=?", (aid,)).fetchone()
    conn.close()
    return row


def get_published(limit=50, offset=0, lang="en"):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM articles WHERE status='published' AND lang=? ORDER BY published_at DESC LIMIT ? OFFSET ?",
        (lang, limit, offset),
    ).fetchall()
    conn.close()
    return rows


def stats(lang=None):
    conn = get_db()
    if lang:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS c FROM articles WHERE lang=? GROUP BY status", (lang,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT status, COUNT(*) AS c FROM articles GROUP BY status").fetchall()
    conn.close()
    return {r["status"]: r["c"] for r in rows}


def save_rewrite(aid, r_title, r_text, provider):
    conn = get_db()
    conn.execute(
        "UPDATE articles SET rewritten_title=?, rewritten_text=?, provider=?, status='pending_approval' WHERE id=?",
        (r_title, r_text, provider, aid),
    )
    conn.commit()
    conn.close()


def save_manual_edit(aid, r_title, r_text, publish=False):
    conn = get_db()
    conn.execute(
        "UPDATE articles SET rewritten_title=?, rewritten_text=?, provider='human' WHERE id=?",
        (r_title, r_text, aid),
    )
    if publish:
        conn.execute(
            "UPDATE articles SET status='published', published_at=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), aid),
        )
    conn.commit()
    conn.close()


def set_status(aid, status):
    conn = get_db()
    if status == "published":
        conn.execute(
            "UPDATE articles SET status=?, published_at=? WHERE id=?",
            (status, datetime.now(timezone.utc).isoformat(), aid),
        )
    else:
        conn.execute("UPDATE articles SET status=? WHERE id=?", (status, aid))
    conn.commit()
    conn.close()


def set_progress(aid, pct):
    pct = max(0, min(100, int(pct)))
    conn = get_db()
    conn.execute("UPDATE articles SET progress=? WHERE id=?", (pct, aid))
    conn.commit()
    conn.close()


def reset_to_pending(aid):
    set_status(aid, "pending_approval")
