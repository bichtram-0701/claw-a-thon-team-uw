"""LLM helpers: narrative report + intent classification, with offline fallbacks.

Env config (injected by the deploy workflow): LLM_API_KEY, LLM_BASE_URL, LLM_MODEL.
Every LLM call degrades gracefully — the agent never breaks if MaaS is down.
"""
import os

VALID_INTENTS = ["summary", "flagged", "province", "segment", "report", "help"]


_MODEL_CACHE: dict = {}


def _client():
    api_key = os.environ.get("LLM_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL")
    model = os.environ.get("LLM_MODEL") or _MODEL_CACHE.get("name")
    if not (api_key and base_url):
        return None, None
    from openai import OpenAI
    # Hard cap well below the platform gateway timeout, so fallbacks fire
    # while we can still answer the request.
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=18)
    if not model:  # auto-discover: prefer a Qwen model from /models
        try:
            ids = [m.id for m in client.models.list()]
            pref = [i for i in ids if "qwen" in i.lower()] or ids
            model = pref[0] if pref else None
            _MODEL_CACHE["name"] = model
        except Exception:  # noqa: BLE001
            return None, None
    if not model:
        return None, None
    return client, model


<<<<<<< HEAD
def llm_chat(system: str, user: str, max_tokens: int = 600) -> str | None:
    """One LLM call; returns None on any failure (caller falls back)."""
=======
_MODEL_OVERRIDE = None  # set when the configured model name 404s and we autodiscover


def _call(client, model, system, user, max_tokens):
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0.3,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content


def _discover_model(client) -> str | None:
    """Ask the serving endpoint for its real model ids; prefer qwen, then gemma."""
    ids = [m.id for m in client.models.list().data]
    return (next((i for i in ids if "qwen" in i.lower()), None)
            or next((i for i in ids if "gemma" in i.lower()), None)
            or (ids[0] if ids else None))


def llm_chat(system: str, user: str, max_tokens: int = 900) -> str | None:
    """One LLM call; self-heals wrong model names; returns None on failure."""
    global _MODEL_OVERRIDE
    client, model = _client()
    if client is None:
        return None
    model = _MODEL_OVERRIDE or model
>>>>>>> d6e4c853333c851946a1b1cbd5ec432356bd916a
    try:
        return _call(client, model, system, user, max_tokens)
    except Exception as e:  # noqa: BLE001
        if "not found" in str(e).lower() or "404" in str(e):
            try:
                pick = _discover_model(client)
                if pick and pick != model:
                    print(f"Model '{model}' not found; switching to '{pick}'")
                    _MODEL_OVERRIDE = pick
                    return _call(client, pick, system, user, max_tokens)
            except Exception as e2:  # noqa: BLE001
                print(f"Model autodiscovery failed ({e2})")
        print(f"LLM call failed ({e}); falling back")
        return None


def classify_intent(message: str) -> str | None:
    """LLM intent routing when keyword routing misses. Returns None offline."""
    out = llm_chat(
        "Classify the user's question about a loan portfolio into exactly one word from: "
        "summary, flagged, province, segment, report, help. "
        "flagged = at-risk accounts/alerts; province = regional breakdown; "
        "segment = product/segment breakdown; report = full written report; "
        "summary = overall health numbers; help = anything else. Reply with the single word only.",
        message, max_tokens=8)
    if out:
        word = out.strip().lower().split()[0].strip(".,!")
        if word in VALID_INTENTS:
            return word
    return None


def _fmt_vnd(v):
    return f"{v/1e9:,.1f}B VND" if v >= 1e9 else f"{v/1e6:,.0f}M VND"


def build_facts(metrics: dict, delta: dict | None) -> str:
    lines = [
        f"As-of date: {metrics.get('as_of_date', 'n/a')}",
        f"Loans: {metrics['loans']:,} | Total outstanding: {_fmt_vnd(metrics['total_outstanding_vnd'])}",
        f"NPL ratio (90+ DPD, by balance): {metrics['npl_ratio_pct']}%",
        f"Total delinquency (1+ DPD): {metrics['delinquency_ratio_pct']}%",
        "DPD buckets (% of balance): " + ", ".join(f"{b['bucket']}: {b['balance_pct']}%" for b in metrics["dpd_buckets"]),
        "By product: " + ", ".join(f"{x['name']}: {x['balance_pct']}%" for x in metrics["by_product"]),
        "By region: " + ", ".join(f"{x['name']}: {x['balance_pct']}%" for x in metrics["by_region"]),
    ]
    if metrics.get("wavg_interest_rate_pct") is not None:
        lines.append(f"Weighted avg interest rate: {metrics['wavg_interest_rate_pct']}%")
    if delta:
        lines.append(
            f"vs previous period: NPL {delta['npl_ratio_pp']:+}pp, delinquency {delta['delinquency_ratio_pp']:+}pp, "
            f"outstanding growth {delta['outstanding_growth_pct']:+}%, loans {delta['loan_count_change']:+,}")
    return "\n".join(lines)


REPORT_SYSTEM = {
    "vi": ("Ban la chuyen vien phan tich rui ro tin dung cao cap. Viet bao cao danh gia danh muc cho vay "
           "bang tieng Viet, ngan gon, chuyen nghiep, dang markdown voi cac muc: Tom tat (3-4 cau), "
           "Chat luong danh muc, Xu huong, Canh bao & Khuyen nghi (toi da 4 gach dau dong). "
           "CHI dung so lieu trong fact sheet, KHONG bia so lieu."),
    "en": ("You are a senior credit risk analyst. Write a concise, professional loan portfolio review "
           "in markdown with sections: Executive Summary (3-4 sentences), Portfolio Quality, Trends, "
           "Warnings & Recommendations (max 4 bullets). Use ONLY figures from the fact sheet. Never invent numbers."),
}


def fallback_report(metrics: dict, delta: dict | None, lang: str) -> str:
    npl = metrics["npl_ratio_pct"]
    risk = ("cao" if npl > 3 else "trung binh" if npl > 1.5 else "thap") if lang == "vi" else \
           ("elevated" if npl > 3 else "moderate" if npl > 1.5 else "low")
    title = "# Bao cao danh muc tin dung" if lang == "vi" else "# Credit Portfolio Report"
    trend = ""
    if delta:
        trend = (f"\n\n**Xu huong:** NPL {'tang' if delta['npl_ratio_pp'] > 0 else 'giam'} "
                 f"{abs(delta['npl_ratio_pp'])}pp so voi ky truoc; du no thay doi {delta['outstanding_growth_pct']:+}%."
                 if lang == "vi" else
                 f"\n\n**Trend:** NPL {'up' if delta['npl_ratio_pp'] > 0 else 'down'} "
                 f"{abs(delta['npl_ratio_pp'])}pp vs prior period; outstanding {delta['outstanding_growth_pct']:+}%.")
    buckets = "\n".join(f"- {b['bucket']}: {b['balance_pct']}% ({b['loans']:,} loans)" for b in metrics["dpd_buckets"])
    return (f"{title}\n\n*As of {metrics.get('as_of_date', 'n/a')} — template mode (no LLM)*\n\n"
            f"- Loans: {metrics['loans']:,} | Outstanding: {_fmt_vnd(metrics['total_outstanding_vnd'])}\n"
            f"- NPL ratio: **{npl}%** (risk level: {risk})\n"
            f"- Delinquency (1+ DPD): {metrics['delinquency_ratio_pct']}%\n\n"
            f"## DPD buckets\n{buckets}{trend}")


def portfolio_report(metrics: dict, delta: dict | None, lang: str = "vi") -> tuple[str, str]:
    """Full written report: LLM narrative or deterministic fallback. Returns (markdown, mode)."""
    facts = build_facts(metrics, delta)
    out = llm_chat(REPORT_SYSTEM.get(lang, REPORT_SYSTEM["vi"]), f"Fact sheet:\n{facts}")
    if out:
        return out, "llm"
    return fallback_report(metrics, delta, lang), "fallback"


def narrate(question: str, result: dict, lang: str = "vi") -> str | None:
    """Phrase a tool result as a short natural-language answer. None when offline."""
    import json
    sys_p = ("Ban la tro ly phan tich danh muc cho vay. Tra loi cau hoi cua nguoi dung "
             "ngan gon (toi da 5 cau) dua DUY NHAT tren JSON ket qua. Tra loi bang tieng Viet."
             if lang == "vi" else
             "You are a lending portfolio analyst assistant. Answer the user's question concisely "
             "(max 5 sentences) using ONLY the JSON result.")
    return llm_chat(sys_p, f"Question: {question}\nResult JSON:\n{json.dumps(result, ensure_ascii=False)}",
                    max_tokens=300)
