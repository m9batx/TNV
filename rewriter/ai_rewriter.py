import json
import re
import logging
import requests
import config
from config import (
    AI_PROVIDER,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    DASHSCOPE_API_KEY,
    DASHSCOPE_BASE_URL,
    QWEN_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    REWRITE_STYLE,
)

log = logging.getLogger("rewriter")

STYLE_GUIDES = {
    "casual": "casual, conversational tech-blogger tone; short punchy sentences; talk directly to the reader ('you')",
    "professional": "clean professional journalism style; neutral, factual, well-structured paragraphs",
    "explainer": "friendly explainer style that breaks down technical terms in simple language with analogies",
}

PROMPT_TEMPLATE = """You are rewriting a tech news article into an ORIGINAL blog post.

Style: {style_guide}
LANGUAGE: Write the title and body in {language}. Never mix languages.

STRICT RULES:
- Never copy sentences from the source. Rephrase everything.
- Keep every fact, number, company and person name accurate.
- Do not invent facts.
- Length: 250-450 words.
- Output STRICT JSON only, no markdown fences:
{{"title": "...", "body": "..."}}

SOURCE TITLE: {title}

SOURCE ARTICLE:
{article}
"""


def _build_prompt(title, article, lang="en"):
    style_guide = STYLE_GUIDES.get(REWRITE_STYLE, STYLE_GUIDES["casual"])
    language = {"en": "English", "ru": "Russian"}.get(lang, "English")
    return PROMPT_TEMPLATE.format(
        style_guide=style_guide,
        language=language,
        title=title or "(no title)",
        article=article[:6000],
    )


def _parse_json_response(raw):
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("model did not return JSON")
    data = json.loads(raw[start : end + 1])
    if not data.get("title") or not data.get("body"):
        raise ValueError("JSON missing title/body")
    return {"title": data["title"].strip(), "body": data["body"].strip()}


def _call_openai_compat(base_url, api_key, model, prompt, temperature=0.8, on_progress=None):
    if on_progress:
        on_progress(30)
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": 1500,
            "response_format": {"type": "json_object"},
        },
        timeout=120,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    if on_progress:
        on_progress(100)
    return _parse_json_response(content)


def _call_deepseek(prompt, on_progress=None):
    return _call_openai_compat(DEEPSEEK_BASE_URL, DEEPSEEK_API_KEY, DEEPSEEK_MODEL, prompt, on_progress=on_progress)


def _call_qwen(prompt, on_progress=None):
    return _call_openai_compat(DASHSCOPE_BASE_URL, DASHSCOPE_API_KEY, QWEN_MODEL, prompt, on_progress=on_progress)


def _call_ollama(prompt, on_progress=None):
    if on_progress:
        on_progress(5)
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "format": "json",
            "stream": True,
            "keep_alive": "30m",
            "options": {
                "temperature": 0.8,
                "num_thread": 2,
                "num_ctx": 4096,
                "num_predict": 1200,
            },
        },
        stream=True,
        timeout=1800,
    )
    resp.raise_for_status()
    target_chars = max(600, min(len(prompt), 5000) // 2)
    content = []
    received = 0
    last_pct = 5
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        try:
            chunk = json.loads(line)
        except ValueError:
            continue
        delta = chunk.get("message", {}).get("content")
        if delta:
            content.append(delta)
            received += len(delta)
            if on_progress:
                pct = min(95, 8 + 87 * received / target_chars)
                pct = int(pct)
                if pct - last_pct >= 4:
                    on_progress(pct)
                    last_pct = pct
        if chunk.get("done"):
            break
    if on_progress:
        on_progress(100)
    return _parse_json_response("".join(content))


PROVIDERS = {
    "deepseek": (_call_deepseek, lambda: bool(DEEPSEEK_API_KEY)),
    "qwen": (_call_qwen, lambda: bool(DASHSCOPE_API_KEY)),
    "ollama": (_call_ollama, lambda: True),
}


def rewrite_article(title, original_text, lang="en", on_progress=None):
    order = [AI_PROVIDER] + [p for p in ("deepseek", "qwen", "ollama") if p != AI_PROVIDER]
    last_err = None
    for provider in order:
        fn, available = PROVIDERS[provider]
        if not available():
            continue
        try:
            result = fn(_build_prompt(title, original_text, lang), on_progress=on_progress)
            result["provider"] = provider
            return result
        except Exception as e:
            last_err = e
            log.warning("provider %s failed: %s", provider, e)
    raise RuntimeError(f"all AI providers failed, last error: {last_err}")
