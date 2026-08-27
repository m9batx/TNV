import sys
import os
import argparse
import requests
from datetime import datetime
import config
import database as db
from pipeline import run_collect, run_rewrite

DOCS_DIR = config.DOCS_OUT_DIR


def cmd_init(_args):
    db.init_db()
    print(f"database ready at {config.DB_PATH}")


def cmd_collect(_args):
    db.init_db()
    n = run_collect()
    print(f"collected {n} new articles")


def cmd_rewrite(args):
    n = run_rewrite(args.limit, args.lang)
    print(f"rewrote {n} articles -> pending_approval")


def cmd_pending(args):
    rows = db.get_articles_by_status("pending_approval", lang=args.lang)
    if not rows:
        print("nothing pending approval")
        return
    print(f"{len(rows)} article(s) pending:\n")
    for r in rows:
        title = r["rewritten_title"] or r["title"]
        print(f"  [{r['id']}] {(r['lang'] or 'en').upper():2} | {title[:70]}  ({r['source']}, by {r['provider']})")


def cmd_show(args):
    r = db.get_article(args.id)
    if not r:
        sys.exit("article not found")
    print("=" * 70)
    print(f"ID: {r['id']}  STATUS: {r['status']}  SOURCE: {r['source']}")
    print(f"URL: {r['url']}")
    print("-" * 70)
    print(r["rewritten_title"] or "(not rewritten yet)")
    print()
    print(r["rewritten_text"] or "(empty)")
    print("=" * 70)


def _approve_one(aid):
    r = db.get_article(aid)
    if not r:
        print(f"[{aid}] not found")
        return False
    if r["status"] != "pending_approval":
        print(f"[{aid}] skipped, status is '{r['status']}'")
        return False
    db.set_status(aid, "published")
    print(f"[{aid}] APPROVED -> live on website")
    return True


def cmd_approve(args):
    if args.target.lower() == "all":
        rows = db.get_articles_by_status("pending_approval", lang=args.lang)
        count = sum(1 for r in rows if _approve_one(r["id"]))
        print(f"\napproved {count}/{len(rows)}")
    else:
        try:
            aid = int(args.target)
        except ValueError:
            sys.exit("target must be an article id or 'all'")
        _approve_one(aid)


def cmd_reject(args):
    try:
        aid = int(args.id)
    except ValueError:
        sys.exit("id must be an integer")
    db.set_status(aid, "rejected")
    print(f"[{aid}] rejected")


def cmd_export(args):
    rows = db.get_articles_by_status("pending_approval", args.limit, args.lang)
    for r in rows:
        fname = f"article_{r['id']}.md"
        path = f"{DOCS_DIR}\\{fname}"
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {r['rewritten_title']}\n\n")
            f.write(f"- Source: {r['source']} ({r['url']})\n")
            f.write(f"- Rewriter: {r['provider']}\n")
            f.write(f"- Exported: {datetime.now().isoformat()}\n\n---\n\n")
            f.write(r["rewritten_text"] or "")
        print(f"wrote {path}")
    if not rows:
        print("nothing to export")


def cmd_stats(_args):
    s = db.stats()
    for k in ("collected", "pending_approval", "published", "rejected"):
        print(f"  {k:>18}: {s.get(k, 0)}")


def cmd_doctor(_args):
    print("== TechPulse doctor ==\n")

    print(f"[db] {config.DB_PATH}")
    print("     OK - exists\n" if os.path.exists(config.DB_PATH) else "     MISSING - run: python cli.py init\n")

    provider = config.AI_PROVIDER
    print(f"[ai] provider = {provider}")
    if provider == "deepseek":
        ok = bool(config.DEEPSEEK_API_KEY)
        print("     OK - key set\n" if ok else "     MISSING DEEPSEEK_API_KEY in .env\n")
    elif provider == "qwen":
        ok = bool(config.DASHSCOPE_API_KEY)
        print("     OK - key set\n" if ok else "     MISSING DASHSCOPE_API_KEY in .env\n")
    else:
        try:
            r = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            if not models:
                print("     Ollama running but no models - run: ollama pull " + config.OLLAMA_MODEL)
            elif any(m.startswith(config.OLLAMA_MODEL.split(":")[0]) for m in models):
                print(f"     OK - ollama up, models: {', '.join(models)}")
            else:
                print(f"     Ollama up but '{config.OLLAMA_MODEL}' missing - run: ollama pull {config.OLLAMA_MODEL}")
                print(f"     available: {', '.join(models)}")
        except Exception:
            print("     NOT RUNNING - install https://ollama.com then: ollama serve")
            print(f"     and: ollama pull {config.OLLAMA_MODEL}")

    print("\n[sites]")
    for site in config.SITES:
        try:
            r = requests.get(site["rss"], timeout=(5, 5), allow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0"}, stream=True)
            ok = r.status_code == 200
            r.close()
            tag = f"[{(site.get('lang') or 'en').upper()}]"
            print(f"     OK   {tag:5} {site['name']}" if ok else f"     WARN {tag:5} {site['name']} (HTTP {r.status_code})")
        except Exception as e:
            print(f"     FAIL [{(site.get('lang') or 'en').upper():4}] {site['name']} ({e.__class__.__name__})")


def main():
    parser = argparse.ArgumentParser(prog="cli", description="news collector control tool")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init").set_defaults(func=cmd_init)
    sub.add_parser("collect").set_defaults(func=cmd_collect)
    p_rw = sub.add_parser("rewrite")
    p_rw.add_argument("--limit", type=int, default=None)
    p_rw.add_argument("--lang", choices=["en", "ru"], default=None)
    p_rw.set_defaults(func=cmd_rewrite)
    p_pd = sub.add_parser("pending")
    p_pd.add_argument("--lang", choices=["en", "ru"], default=None)
    p_pd.set_defaults(func=cmd_pending)
    p_show = sub.add_parser("show")
    p_show.add_argument("id", type=int)
    p_show.set_defaults(func=cmd_show)
    p_ap = sub.add_parser("approve")
    p_ap.add_argument("target")
    p_ap.add_argument("--lang", choices=["en", "ru"], default=None)
    p_ap.set_defaults(func=cmd_approve)
    p_rj = sub.add_parser("reject")
    p_rj.add_argument("id")
    p_rj.set_defaults(func=cmd_reject)
    p_ex = sub.add_parser("export")
    p_ex.add_argument("--limit", type=int, default=50)
    p_ex.add_argument("--lang", choices=["en", "ru"], default=None)
    p_ex.set_defaults(func=cmd_export)
    sub.add_parser("stats").set_defaults(func=cmd_stats)
    sub.add_parser("doctor").set_defaults(func=cmd_doctor)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
