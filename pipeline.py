import logging
from database import get_articles_by_status, save_rewrite, set_status, set_progress
from scraper.scraper import collect_all
from rewriter.ai_rewriter import rewrite_article
from config import REWRITE_LIMIT_PER_RUN

log = logging.getLogger("pipeline")


def run_collect(lang=None):
    count = collect_all(lang)
    log.info("collect finished (%s), %d new articles", lang or "all", count)
    return count


def run_rewrite(limit=None, lang=None):
    limit = limit or REWRITE_LIMIT_PER_RUN
    for stuck in get_articles_by_status("processing", 2000, lang if lang else None):
        set_status(stuck["id"], "collected")
        set_progress(stuck["id"], 0)
    rows = get_articles_by_status("collected", limit, lang)
    done = 0
    for row in rows:
        aid = row["id"]
        set_status(aid, "processing")
        set_progress(aid, 0)
        try:
            result = rewrite_article(
                row["title"], row["original_text"], row["lang"] or "en",
                on_progress=lambda p, aid=aid: set_progress(aid, p),
            )
            save_rewrite(aid, result["title"], result["body"], result["provider"])
            done += 1
            log.info("rewrote article %d (%s) via %s", aid, row["lang"], result["provider"])
        except Exception as e:
            set_status(aid, "collected")
            set_progress(aid, 0)
            log.error("rewrite failed for article %d: %s", aid, e)
    return done
