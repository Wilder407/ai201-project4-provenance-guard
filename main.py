"""
Provenance Guard — M3: Flask skeleton + Signal 1 (lexical/statistical).

This milestone implements:
  - Flask app + Flask-Limiter on POST /submit
  - compute_lexical_signal() — fully implemented, no model call
  - compute_llm_signal() — STUB ONLY, implemented in M4
  - combine_signals() / threshold check — STUB ONLY, implemented in M4
  - transparency label generation — STUB ONLY, implemented in M5
  - /appeal route — NOT YET BUILT, implemented in M5

POST /submit currently returns the lexical score directly so it can be
tested end-to-end before Signal 2 exists.
"""

import math
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ── App setup ─────────────────────────────────────────────────────────────────

app = Flask(__name__)

# Rate limit values per planning.md: 10/min, 50/hour.
# A human can't meaningfully submit 10 unique pieces in 60 seconds;
# 50/hour blocks systematic scraping while staying generous for real creators.
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

LOG_PATH = Path("logs/audit_log.jsonl")
LOG_PATH.parent.mkdir(exist_ok=True)

# content_id -> record, in-memory for now
submissions: dict[str, dict] = {}


# ── Signal 1: Lexical / Statistical (fully implemented this milestone) ──────

def compute_lexical_signal(text: str) -> dict:
    """
    Measures statistical properties of the raw text directly — no model call.

    Per planning.md, this signal measures:
      - sentence length variance (most discriminative — AI text is uniform)
      - vocabulary diversity (type-token ratio)
      - punctuation patterns (special punctuation richness)
      - hedge word density

    Returns a dict with "score" (0.0-1.0, higher = more likely AI) plus the
    individual sub-metrics, so they can be inspected directly during testing.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s for s in sentences if s]
    words = re.findall(r'\b\w+\b', text.lower())

    if not words or not sentences:
        return {"score": 0.5, "reason": "insufficient text"}

    # --- Vocabulary diversity (Type-Token Ratio) ---
    ttr = len(set(words)) / len(words)
    # TTR < 0.4 -> low diversity (AI-like); > 0.7 -> rich (human-like)
    ttr_score = 1.0 - min(max((ttr - 0.4) / 0.3, 0.0), 1.0)

    # --- Sentence length variance ---
    lengths = [len(re.findall(r'\b\w+\b', s)) for s in sentences]
    if len(lengths) > 1:
        mean_len = sum(lengths) / len(lengths)
        variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
        std_dev = math.sqrt(variance)
        # std_dev < 3 -> very uniform (AI-like); > 10 -> varied (human-like)
        length_variance_score = 1.0 - min(max((std_dev - 3.0) / 7.0, 0.0), 1.0)
    else:
        std_dev = 0.0
        length_variance_score = 0.5

    # --- Punctuation patterns ---
    special_punct = len(re.findall(r'[—–…\(\)\[\];]', text))
    punct_ratio = special_punct / max(len(sentences), 1)
    punct_score = 1.0 - min(punct_ratio / 2.0, 1.0)

    # --- Hedge word density ---
    hedge_words = {
        'perhaps', 'maybe', 'somehow', 'basically', 'honestly', 'actually',
        'anyway', 'literally', 'stuff', 'things', 'really', 'quite', 'like'
    }
    hedge_count = sum(1 for w in words if w in hedge_words)
    hedge_ratio = hedge_count / len(words)
    hedge_score = 1.0 - min(hedge_ratio / 0.08, 1.0)

    # Weighted composite — sentence length variance is most discriminative
    composite = (
        ttr_score              * 0.25
        + length_variance_score * 0.45
        + punct_score           * 0.15
        + hedge_score           * 0.15
    )

    return {
        "score": round(composite, 3),
        "ttr": round(ttr, 3),
        "sentence_length_std_dev": round(std_dev, 2),
        "special_punct_ratio": round(punct_ratio, 3),
        "hedge_ratio": round(hedge_ratio, 3),
    }


# ── Signal 2: LLM Semantic (M4 — implemented this milestone) ─────────────────

import json
import os
import re as _re

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def compute_llm_signal(text: str) -> dict:
    """
    Sends the text to Groq and asks it to assess likely origin at the
    meaning level — per planning.md: emotional authenticity, structural
    predictability, over-polished transitions, felt vs. simulated irregularity.

    Returns a dict with "score" (0.0-1.0, higher = more likely AI), plus
    the model's stated reasoning and notable features for inspection.

    Known blind spot from planning.md: this signal evaluates meaning, so it
    has little to work with on content-free or purely factual text (e.g. a
    flat list of agenda items) — there's no emotional arc or narrative
    structure to assess either way. This is a case to watch in testing.
    """
    prompt = f"""You are an expert at analyzing creative writing to assess whether it was likely written by a human or generated by AI.

Analyze the following piece of writing carefully. Look for:
- Stylistic consistency vs. authentic human irregularity
- Structural predictability (AI tends toward balanced, tidy structures)
- Vocabulary choices (AI tends toward slightly formal, hedged language)
- Emotional authenticity vs. simulated emotion
- Idiosyncratic errors, typos, or unexpected turns that suggest human origin
- Over-polished transitions and paragraph structures

Respond ONLY with valid JSON. No preamble. No explanation outside the JSON.

{{
  "ai_probability": <float 0.0 to 1.0, where 1.0 = almost certainly AI>,
  "reasoning": "<2-3 sentence explanation of the most decisive signals you observed>",
  "notable_features": ["<feature 1>", "<feature 2>", "<feature 3>"]
}}

TEXT TO ANALYZE:
\"\"\"
{text[:3000]}
\"\"\"
"""

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.1,
    )

    raw = response.choices[0].message.content.strip()
    raw = _re.sub(r'^```(?:json)?\s*', '', raw)
    raw = _re.sub(r'\s*```$', '', raw)

    parsed = json.loads(raw)

    return {
        "score": round(float(parsed["ai_probability"]), 3),
        "reasoning": parsed.get("reasoning", ""),
        "notable_features": parsed.get("notable_features", []),
    }


# ── Combiner / threshold check (M4 — implemented this milestone) ────────────

SHORT_TEXT_WORD_THRESHOLD = 60
SHORT_TEXT_CONFIDENCE_CAP = 0.6


def combine_signals(lexical: dict, llm: dict, word_count: int) -> tuple[str, float]:
    """
    Combines the two signals into a final attribution + confidence, per
    planning.md:

      weighted_score = lexical_score * 0.35 + llm_score * 0.65

      >= 0.75 -> ai_generated   (confidence = weighted_score)
      <= 0.35 -> human_written  (confidence = 1 - weighted_score)
      else    -> uncertain      (confidence = 0.5 + distance from midpoint)

    The LLM signal is weighted higher because it evaluates meaning, which is
    harder to fake than surface statistics. The asymmetric thresholds exist
    because a false positive (calling human work AI) is worse than a false
    negative.

    SHORT-TEXT SAFEGUARD (added after M4 testing surfaced a real false
    positive): short, low-information text (e.g. flat lists, terse notes)
    gives both signals very little to work with, and both signals can fail
    in the same direction at once — agreeing confidently that uniform,
    content-free human writing is AI-generated. Weighting can't fix this,
    because the signals aren't disagreeing; they're both wrong together.

    So: if word_count < 60 AND the verdict would be ai_generated, confidence
    is capped at 0.6. The attribution is left as ai_generated rather than
    forced to uncertain, but the capped confidence signals to the reader
    that this verdict carries real doubt. The cap only applies on the
    ai_generated side, consistent with the asymmetric design — a false
    positive is the worse error, so it's the one we actively guard against.
    Short human_written or uncertain results are left uncapped, since the
    risk there is lower.
    """
    ai_score = lexical["score"] * 0.35 + llm["score"] * 0.65

    if ai_score >= 0.75:
        attribution = "ai_generated"
        confidence = ai_score
        if word_count < SHORT_TEXT_WORD_THRESHOLD:
            confidence = min(confidence, SHORT_TEXT_CONFIDENCE_CAP)
    elif ai_score <= 0.35:
        attribution = "human_written"
        confidence = 1.0 - ai_score
    else:
        attribution = "uncertain"
        distance_from_center = abs(ai_score - 0.55)
        confidence = 0.5 + distance_from_center

    return attribution, round(confidence, 3)


# ── Transparency label (STUB — built in M5) ──────────────────────────────────

def generate_transparency_label(attribution, confidence) -> str | None:
    """
    STUB for M5. Will return one of the three exact label variants from
    planning.md. Not implemented yet.
    """
    return None


# ── Audit logging ─────────────────────────────────────────────────────────────

def write_log(entry: dict) -> None:
    import json
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute; 50 per hour")
def submit_content():
    """
    M4 scope: both signals + combined attribution/confidence are now real.
    transparency_label is still stubbed as None until M5.
    """
    data = request.get_json(silent=True)
    if not data or "content" not in data:
        return jsonify({"error": "Request body must include 'content'."}), 400

    content = data["content"]
    if len(content) < 50:
        return jsonify({"error": "Content must be at least 50 characters."}), 400
    if len(content) > 10_000:
        return jsonify({"error": "Content must be 10,000 characters or fewer."}), 400

    content_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now(timezone.utc).isoformat()

    lexical = compute_lexical_signal(content)
    llm = compute_llm_signal(content)
    word_count = len(_re.findall(r'\b\w+\b', content))
    attribution, confidence = combine_signals(lexical, llm, word_count)
    label = generate_transparency_label(attribution, confidence)  # stub, returns None until M5

    record = {
        "content_id": content_id,
        "creator_id": data.get("creator_id"),
        "title": data.get("title"),
        "attribution": attribution,
        "confidence": confidence,
        "transparency_label": label,       # null until M5
        "signals": {
            "lexical": lexical,
            "llm_classifier": llm,
        },
        "status": "classified",
        "timestamp": timestamp,
    }

    submissions[content_id] = record

    write_log({
        "event": "classification",
        "content_id": content_id,
        "lexical_score": lexical.get("score"),
        "llm_score": llm.get("score"),
        "timestamp": timestamp,
    })

    return jsonify(record), 200


@app.route("/status/<content_id>", methods=["GET"])
def get_status(content_id):
    """Retrieve a submission record. Built early since /submit needs somewhere
    to point testers — full appeal-aware version comes in M5."""
    if content_id not in submissions:
        return jsonify({"error": "Content ID not found."}), 404
    return jsonify(submissions[content_id]), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "milestone": "M3"}), 200


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "Rate limit exceeded.", "detail": str(e.description)}), 429


if __name__ == "__main__":
    app.run(debug=True, port=5000)