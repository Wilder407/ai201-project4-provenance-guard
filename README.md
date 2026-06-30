# ai201-project4-provenance-guard

# Provenance Guard

A backend attribution system for creative content platforms. Classifies submitted text as human-written, AI-generated, or uncertain — with confidence scoring, transparency labels, an appeals workflow, rate limiting, and structured audit logging.

---

## Quick Start

```bash
pip install -r requirements.txt

# Add your Groq key to a .env file:
echo "GROQ_API_KEY=your_key_here" > .env

python main.py
```

API runs at `http://localhost:5000`. To generate sample audit log entries, run `python demo.py` while the server is running.

---

## System Overview

Provenance Guard accepts a piece of text, runs it through two independent detection signals, combines them into a confidence-scored attribution, and returns a plain-language transparency label suitable for display to readers. Creators can appeal decisions they believe are wrong.

---

## Multi-Signal Detection Pipeline

The system uses two distinct signals, chosen because they fail in different directions — catching each other's blind spots.

### Signal 1: Lexical / Statistical Heuristics (weight: 0.35)

**What it captures:** Low-level statistical properties of the text, independent of meaning.

| Heuristic | What it measures | AI pattern |
|---|---|---|
| Type-Token Ratio (TTR) | Vocabulary diversity | AI text reuses vocabulary more uniformly |
| Sentence length variance | Rhythm irregularity | AI has suspiciously uniform sentence lengths |
| Special punctuation ratio | Idiosyncratic punct. use | AI uses em-dashes/ellipses sparingly and evenly |
| Hedge word density | Informal hedging | Polished AI text often has zero hedges |

These are computed locally with no API call. **Sentence length variance is the most discriminative** — human writers write one-word sentences and then sprawling compounds; AI tends toward uniform clause structure.

**Limitation:** Gameable by an adversarial writer who deliberately varies sentence length. That's why this signal alone isn't sufficient.

### Signal 2: LLM Semantic Classifier (weight: 0.65)

**What it captures:** Semantic and structural patterns at the meaning level — whether the emotional arc feels authentic, whether transitions are too clean, whether the piece has the kind of productive messiness that human writers produce.

Claude is prompted to return a structured `ai_probability` float (0–1) with reasoning. This catches what statistics miss: a poem that scans perfectly but lacks the felt irregularity of lived emotion; an essay with suspiciously tidy thesis-support-conclusion structure.

**Weight is higher (0.65)** because it operates at the level of meaning, not surface statistics. However, it has its own failure modes — it can be fooled by intentionally rough writing, and may over-flag non-native English speakers. The uncertain zone and appeals process exist partly for this reason.

### Signal Combination

```
weighted_score = lexical_score × 0.35 + llm_score × 0.65
```

---

## Confidence Scoring with Uncertainty

**Design decision:** Confidence should reflect genuine epistemic state, not false precision.

### Threshold Design (Asymmetric)

The spec hint notes that false positives (labeling a human's work AI) are worse than false negatives. The threshold design reflects this:

| Raw AI Score | Attribution | Confidence | Meaning |
|---|---|---|---|
| ≥ 0.75 | `ai_generated` | = ai_score | Strong signal, high bar to clear |
| ≤ 0.35 | `human_written` | = 1 − ai_score | Strong signal in other direction |
| 0.36 – 0.74 | `uncertain` | 0.5 + distance from 0.55 | Honest acknowledgment of ambiguity |

**Why 0.75, not 0.5?** A 0.51 score and a 0.74 score are both labeled `uncertain`. The system will only issue an `ai_generated` verdict when the evidence is strong. This protects creators at the cost of leaving some AI content unlabeled — a deliberate tradeoff.

### Testing Score Meaningfulness

Scores were verified against three real samples, not hypothetical ones: a Maya Angelou excerpt (known human, literary), a ChatGPT-generated paragraph on work-life balance (known AI), and a piece of original writing built specifically as an edge case (a flat, repetitive meeting agenda).

| Sample | Lexical score | LLM score | Result |
|---|---|---|---|
| Maya Angelou excerpt | 0.605 | 0.10 | `human_written`, confidence 0.723 |
| ChatGPT-generated paragraph | 0.750 | 0.85 | `ai_generated`, confidence 0.815 |
| Original edge-case agenda | 0.778 | 0.95 | `ai_generated`, confidence 0.6 (see safeguard below) |

The first two results validate the system: known human writing scored low, known AI writing scored high, and the LLM's stated reasoning matched what a human reviewer would notice (Angelou's "distinctive, idiomatic style" and "metaphor and rhetorical questions" vs. the ChatGPT sample's "clichéd expressions" and "lack of human irregularity").

The third result is more important — it's where testing found a real failure, not a synthetic one.

### Short-Text Confidence Safeguard

The edge-case sample was deliberately written to be human but stylistically uniform: short, repetitive, declarative sentences with no emotional content ("The meeting starts at nine o'clock. The agenda has five items..."). Both signals agreed it was AI-generated — the lexical signal flagged the low sentence-length variance, and the LLM signal flagged the lack of emotional authenticity and "formulaic sentence structure." Before any safeguard, this produced `ai_generated` at **0.89 confidence** — a confident, wrong verdict on genuinely human writing.

This is a meaningful failure because it isn't a disagreement between signals that a weighted average can resolve. Both signals failed in the *same direction* on the same blind spot: short, low-information, terse human writing gives both signals very little to work with, and both default toward reading that absence of irregularity as evidence of AI origin.

**Fix:** a word-count safeguard was added to `combine_signals`. If a submission is under 60 words *and* the combined score would produce an `ai_generated` verdict, confidence is capped at 0.6 rather than left uncapped. The cap is scoped only to the `ai_generated` side, consistent with the system's asymmetric threshold philosophy — a confident false positive against a human writer is the error this system is built to avoid, so it's the one actively guarded against. Short `human_written` or `uncertain` results are left uncapped, since a human writer being told (with appropriate uncertainty) that their work might be AI is a smaller harm than the reverse, and over-correcting there would blunt the system's ability to flag short AI content at all.

Re-running the same edge case after the fix, with identical underlying signal scores:

| | Before fix | After fix |
|---|---|---|
| Attribution | `ai_generated` | `ai_generated` |
| Confidence | 0.89 | **0.6** |

The verdict didn't change — the system still leans toward AI on this sample, which is defensible given what both signals independently found. What changed is what that verdict communicates: 0.89 reads as near-certainty to a user, while 0.6 reads as a much more honest "we lean this way, but we're not sure." That distinction matters most exactly when the system is wrong.

**Known residual limitation:** this safeguard caps confidence but doesn't change the underlying attribution. A short, genuinely human, low-emotional-content piece will still be labeled `ai_generated`, just with capped confidence rather than high confidence. A repetition-detection signal (distinct from raw word count) is a natural next improvement, documented as a stretch goal rather than built under deadline pressure.

---

## Transparency Label Variants

The label is the user-facing output. All three variants:

### Variant 1: High-Confidence AI (`ai_generated`)

```
⚠️ Likely AI-Generated (82% confidence)
Our analysis suggests this content was probably created with an AI writing tool.
This is based on automated signals and may not be accurate.
If you are the creator and believe this is wrong, you can submit an appeal.
```

*(Confidence percentage varies; the structure is constant.)*

### Variant 2: High-Confidence Human (`human_written`)

```
✅ Likely Human-Written (79% confidence)
Our analysis suggests this content was written by a person.
No automated system is perfect — this reflects our best assessment, not a guarantee.
```

### Variant 3: Uncertain

```
🔍 Origin Unclear
We were unable to confidently determine whether this content was written by a human
or generated by AI. It shows characteristics of both.
Treat this content as you would any unverified source.
```

**Design rationale:** The uncertain label deliberately gives no confidence percentage because the number would be misleading ("51% confidence" sounds almost-certain but is actually near-random). The AI label always includes an appeal path. The human label includes an epistemic caveat — we're not guaranteeing anything.

---

## Appeals Workflow

Creators can contest any classification. The endpoint is:

```
POST /appeal/{content_id}
{
  "creator_id": "user_abc",
  "reasoning": "I wrote this myself — here's why the system is wrong..."
}
```

**What an appeal does:**
1. Validates the content ID exists
2. Records the creator's reasoning alongside the original decision
3. Sets `status = "under_review"`
4. Writes a structured audit log entry
5. Returns confirmation with the appeal record

**What an appeal does NOT do:** Trigger automatic re-classification. Reasons:
- Re-running the same signals on the same text produces the same result
- A human moderator needs context the system can't see: drafts, revision history, the creator's track record
- Automated re-classification creates a gaming surface (submit appeals until you get a favorable result)

Human moderators retrieve under-review items via `GET /status/{content_id}`.

---

## Rate Limiting

Rate limits are applied per IP address at the submission endpoint.

| Window | Limit | Reasoning |
|---|---|---|
| Per minute | 10 | A human can't meaningfully write and submit 10 unique pieces in 60 seconds |
| Per hour | 50 | Generous for any legitimate creator; blocks systematic API scraping |

**Reasoning process:** A real creator might submit a revised poem, a short story, and a blog draft in one session — maybe 5–10 items over an hour. An adversary probing the classifier's behavior would need 100+ submissions to map the decision boundary. The 10/min limit blocks floods while giving legitimate users headroom. The 50/hour limit is a secondary ceiling.

Returns `HTTP 429` with a descriptive message when exceeded.

---

## Audit Log

Every classification and appeal is written to `logs/audit_log.jsonl` (append-only, one JSON object per line).

### Classification entry format:
```json
{
  "event": "classification",
  "content_id": "a1b2c3d4",
  "attribution": "human_written",
  "confidence": 0.712,
  "lexical_score": 0.241,
  "llm_score": 0.198,
  "timestamp": "2025-06-14T22:31:05.123456+00:00"
}
```

### Appeal entry format:
```json
{
  "event": "appeal_submitted",
  "content_id": "e5f6g7h8",
  "creator_id": "user_abc",
  "original_attribution": "ai_generated",
  "original_confidence": 0.821,
  "appeal_reasoning_length": 287,
  "timestamp": "2025-06-14T22:35:11.445221+00:00"
}
```

### Sample log output (3 entries, from `GET /log`):

```json
{"event": "classification", "content_id": "3f9a1c2b", "attribution": "human_written", "confidence": 0.724, "lexical_score": 0.22, "llm_score": 0.19, "timestamp": "2025-06-14T22:01:11+00:00"}
{"event": "classification", "content_id": "7d4e8b5f", "attribution": "ai_generated", "confidence": 0.831, "lexical_score": 0.74, "llm_score": 0.88, "timestamp": "2025-06-14T22:02:44+00:00"}
{"event": "appeal_submitted", "content_id": "7d4e8b5f", "creator_id": "user_anonymous_7", "original_attribution": "ai_generated", "original_confidence": 0.831, "appeal_reasoning_length": 312, "timestamp": "2025-06-14T22:04:02+00:00"}
{"event": "classification", "content_id": "2a6c9d1e", "attribution": "uncertain", "confidence": 0.571, "lexical_score": 0.41, "llm_score": 0.58, "timestamp": "2025-06-14T22:06:18+00:00"}
```

*(Live entries generated by running `demo.py` after starting the server.)*

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/submit` | Submit content for classification |
| POST | `/appeal/<id>` | Submit an appeal |
| GET | `/status/<id>` | Get classification + status |
| GET | `/log` | Get audit log entries |
| GET | `/health` | Health check |

### `POST /submit` — request body:
```json
{
  "content": "Your text here (50–10,000 chars)",
  "creator_id": "optional_string",
  "title": "optional_string"
}
```

### `POST /submit` — response:
```json
{
  "content_id": "3f9a1c2b",
  "attribution": "human_written",
  "confidence": 0.724,
  "transparency_label": "✅ Likely Human-Written (72% confidence)\n...",
  "signals": {
    "lexical": { "score": 0.22, "ttr": 0.61, ... },
    "llm_classifier": { "score": 0.19, "reasoning": "...", "notable_features": [...] }
  },
  "timestamp": "2025-06-14T22:01:11+00:00"
}
```

---

## Known Limitations

- **AI detection is an unsolved problem.** Scores reflect probabilistic signals, not ground truth.
- **LLM classifier bias:** Claude may over-flag polished non-native English writing or under-flag intentionally rough AI output.
- **Short texts:** Heuristics are less reliable under ~100 words. The system is calibrated for poems, essays, and story excerpts (50–10,000 chars).
- **No persistence:** Submissions live in memory; restart clears them. A production version would use a database.
- **Rate limits by IP:** Shared IPs (e.g., university networks) could hit limits from multiple legitimate users. Production would use authenticated user IDs.