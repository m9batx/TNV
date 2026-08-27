import logging
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, abort, flash
import config
import database as db
from pipeline import run_collect, run_rewrite
from rewriter.ai_rewriter import rewrite_article

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return wrapper


@app.route("/")
def index():
    articles = db.get_published(limit=30, lang="en")
    return render_template("index.html", articles=articles, lang="en", langs=config.LANGUAGES)


@app.route("/ru")
def index_ru():
    articles = db.get_published(limit=30, lang="ru")
    return render_template("index.html", articles=articles, lang="ru", langs=config.LANGUAGES)


@app.route("/article/<int:aid>")
def article(aid):
    a = db.get_article(aid)
    if not a or a["status"] != "published":
        abort(404)
    paragraphs = [p for p in (a["rewritten_text"] or "").split("\n\n") if p.strip()]
    return render_template("article.html", a=a, paragraphs=paragraphs)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == config.ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin"))
        flash("Wrong password")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin")
@login_required
def admin():
    status = request.args.get("status", "pending_approval")
    lang = request.args.get("lang", "all")
    if status not in config.STATUSES:
        status = "pending_approval"
    if lang not in ("all", "en", "ru"):
        lang = "all"
    articles = db.get_articles_by_status(status, lang=None if lang == "all" else lang)
    return render_template(
        "admin.html",
        articles=articles,
        current_status=status,
        current_lang=lang,
        statuses=config.STATUSES,
        stats=db.stats(),
    )


@app.route("/admin/approve/<int:aid>", methods=["POST"])
@login_required
def approve(aid):
    db.set_status(aid, "published")
    return redirect(request.referrer or url_for("admin"))


@app.route("/admin/reject/<int:aid>", methods=["POST"])
@login_required
def reject(aid):
    db.set_status(aid, "rejected")
    return redirect(request.referrer or url_for("admin"))


@app.route("/admin/repending/<int:aid>", methods=["POST"])
@login_required
def repending(aid):
    db.reset_to_pending(aid)
    return redirect(request.referrer or url_for("admin"))


@app.route("/admin/collect", methods=["POST"])
@login_required
def collect():
    import threading

    lang = request.form.get("lang", "all")
    if lang not in ("all", "en", "ru"):
        lang = "all"
    scope = {"all": "all languages", "en": "English sources", "ru": "Russian sources"}[lang]

    def job():
        try:
            n = run_collect(None if lang == "all" else lang)
            app.logger.info("background collect (%s): %d new", lang, n)
            m = run_rewrite(limit=n if n > 0 else None, lang=None if lang == "all" else lang)
            app.logger.info("auto-rewrote %d articles (%s) -> pending_approval", m, lang)
        except Exception as e:
            app.logger.error("collect+rewrite pipeline failed: %s", e)

    threading.Thread(target=job, daemon=True).start()
    flash(f"Pipeline started ({scope}): collecting, then AI-rewriting new articles. "
          f"They will appear under Pending Approval as they finish (~2 min each).")
    return redirect(url_for("admin", status="pending_approval", lang=lang))


@app.route("/admin/rewrite", methods=["POST"])
@login_required
def rewrite():
    import threading

    lang = request.form.get("lang", "all")
    if lang not in ("all", "en", "ru"):
        lang = "all"

    def job():
        try:
            n = run_rewrite(lang=None if lang == "all" else lang)
            app.logger.info("background rewrite (%s) finished: %d done", lang, n)
        except Exception as e:
            app.logger.error("background rewrite failed: %s", e)

    threading.Thread(target=job, daemon=True).start()
    scope = {"all": "queue", "en": "EN queue", "ru": "RU queue"}[lang]
    flash(f"Rewriting {scope} in background - refresh in a few minutes")
    return redirect(url_for("admin", status="pending_approval", lang=lang))


@app.route("/admin/rerewrite/<int:aid>", methods=["POST"])
@login_required
def rerewrite(aid):
    import threading

    def job():
        try:
            a = db.get_article(aid)
            db.set_status(aid, "processing")
            db.set_progress(aid, 0)
            result = rewrite_article(
                a["title"], a["original_text"], a["lang"] or "en",
                on_progress=lambda p: db.set_progress(aid, p),
            )
            db.save_rewrite(aid, result["title"], result["body"], result["provider"])
            app.logger.info("re-rewrote article %d via %s", aid, result["provider"])
        except Exception as e:
            db.set_status(aid, "collected")
            db.set_progress(aid, 0)
            app.logger.error("re-rewrite failed for article %d: %s", aid, e)

    threading.Thread(target=job, daemon=True).start()
    flash(f"Article #{aid} is being rewritten by AI - refresh in ~2 min")
    return redirect(request.referrer or url_for("admin"))


@app.route("/admin/edit/<int:aid>", methods=["GET", "POST"])
@login_required
def edit_article(aid):
    a = db.get_article(aid)
    if not a:
        abort(404)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        if not title or not body:
            flash("Title and body cannot be empty")
            return render_template("edit.html", a=a)
        publish = request.form.get("action") == "publish"
        db.save_manual_edit(aid, title, body, publish=publish)
        flash(f"Article #{aid} saved manually{' and published' if publish else ''}")
        return redirect(url_for("admin"))
    return render_template("edit.html", a=a)


def start_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(max_instances=2)
    scheduler.add_job(run_collect, "interval", minutes=config.COLLECT_INTERVAL_MINUTES,
                      id="collect", misfire_grace_time=600)
    scheduler.add_job(run_rewrite, "interval", minutes=config.REWRITE_INTERVAL_MINUTES,
                      id="rewrite", misfire_grace_time=600)
    scheduler.start()
    app.logger.info("scheduler started")
    return scheduler


if __name__ == "__main__":
    db.init_db()
    start_scheduler()
    from waitress import serve

    print(f"* TechPulse running at http://{config.HOST}:{config.PORT}")
    print(f"* Admin dashboard:  http://{config.HOST}:{config.PORT}/admin")
    print("* Press CTRL+C to stop")
    serve(app, host=config.HOST, port=config.PORT, threads=4)
