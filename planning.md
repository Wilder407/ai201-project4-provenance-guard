# Provenance Guard — Planning

## Architecture Narrative

A piece of text is submitted to `POST /submit`. Before anything else, `Flask-Limiter` checks whether the user has exceeded the request limit. Then two signals run on the text. The first, the lexical signal, measures the statistical properties of the raw text (sentence length variance, vocabulary diversity, punctuation patterns, hedge word density) without any model call. The second, the LLM signal, sends the text to Groq and asks it to assess the likely origin at the meaning level. Each signal returns a score between 0 and 1. These two scores are combined — the LLM signal is weighted higher because it evaluates for meaning within the text, not just surface statistics. The combined score is passed to a threshold check: if it is above 0.75 the content is labeled AI-generated, below 0.35 it is labeled human-written, and in between it is labeled uncertain because there is not strong evidence in either direction. That label and score go to the label generator, which writes a plain-English label. Finally, the decision is written to the audit log and the full response is returned to the caller.

---

## Architecture Diagram

```
                          Client / Platform
                               │
                               ▼
                    ┌──────────────────────┐
                    │   POST /submit       │
                    │  Flask-Limiter check │
                    └──────────┬───────────┘
                               │ raw text
               ┌───────────────┴───────────────┐
               │                               │
               ▼                               ▼
   ┌───────────────────────┐     ┌──────────────────────────┐
   │  Signal 1: Lexical    │     │  Signal 2: LLM           │
   │  (no model call)      │     │  (Groq API)              │
   │                       │     │                          │
   │  sentence length var  │     │  meaning-level assess-   │
   │  vocabulary diversity │     │  ment of likely origin   │
   │  punctuation patterns │     │                          │
   │  hedge word density   │     │  → ai_probability 0–1    │
   │                       │     └──────────────┬───────────┘
   │  → score 0–1          │                    │
   └──────────────┬────────┘                    │
                  │ score (×0.35)               │ score (×0.65)
                  └──────────────┬──────────────┘
                                 │ weighted combined score
                                 ▼
               ┌─────────────────────────────────┐
               │    Threshold Check              │
               │                                 │
               │  ≥ 0.75 → ai_generated          │
               │  ≤ 0.35 → human_written         │
               │  else   → uncertain             │
               └──────────────┬──────────────────┘
                              │ attribution + confidence
                              ▼
               ┌─────────────────────────────────┐
               │    Transparency Label Generator │
               │    (plain-English, 3 variants)  │
               └──────────────┬──────────────────┘
                              │
                    ┌─────────┴──────────┐
                    │                    │
                    ▼                    ▼
            JSON response          Audit Log
            to caller              (audit_log.jsonl)


Appeal Flow:

  Creator → POST /appeal/<id> → validate ID exists
                             → record reasoning + original decision
                             → set status = "under_review"
                             → write to audit log
                             → return confirmation
                               (human moderator reviews offline)
```

---

## Detection Signals

Both signals output a continuous score between 0 and 1 (not a binary flag), where higher values indicate greater likelihood of AI origin. This is deliberate — a binary flag per signal would throw away the magnitude information needed for honest confidence scoring later in the pipeline.

### Signal 1: Lexical / Statistical (weight: 0.35)

**What it measures:** Low-level statistical properties of the raw text, computed directly without any model call.

| Metric | What it captures |
|---|---|
| Sentence length variance (std dev) | AI text has suspiciously uniform sentence lengths; human writing varies |
| Type-Token Ratio (TTR) | Vocabulary diversity — AI output tends toward uniform word reuse |
| Special punctuation ratio | Humans use em-dashes, ellipses, parentheses idiosyncratically |
| Hedge word density | Polished AI text often contains zero informal hedges |

**Why these properties differ:** Human writers vary naturally — they write fragments, run-ons, and everything in between. AI models are trained to produce balanced, readable output, which shows up as statistical regularity.

**Blind spot:** A formal human writer — an academic, a lawyer, someone trained under a strict style guide — has a natural style that shares statistical properties with AI output. Uniform sentence lengths and low hedge density are not exclusive to AI; they describe disciplined human writing too. The signal cannot distinguish between the two.

**Weight is lower (0.35)** because this signal is gameable and unreliable on short texts.

---

### Signal 2: LLM Semantic Classifier (weight: 0.65)

**What it measures:** Likely origin at the meaning level — whether the emotional arc feels authentic, whether ideas connect the way a person's thoughts connect, whether structure is too neat to be spontaneous.

**Why this differs:** Statistical regularity can be mimicked by disciplined humans, but the quality of felt irregularity in human writing — the productive mess of real thought — is harder to fake. The LLM assesses whether the piece reads as genuinely experienced or constructed.

**Blind spot:** AI-generated content that has been deliberately edited to appear human — with added typos, fragmented sentences, or informal interjections inserted after generation — may read as authentic at the meaning level. The LLM can be fooled by surface roughness that mimics human spontaneity.

**Weight is higher (0.65)** because it operates at the level of meaning rather than surface statistics.

---

### Signal Combination

```
weighted_score = lexical_score × 0.35 + llm_score × 0.65
```

The two signals are designed to fail in different directions. The lexical signal catches statistical regularity that the LLM might rationalize as style. The LLM catches meaning-level patterns that statistics cannot see. Together they are more robust than either alone.

---

## Confidence Scoring & Thresholds

**Design principle:** Confidence should reflect genuine epistemic state. A score of 0.5 means the system genuinely does not know — not "slightly AI."

### Asymmetric thresholds

Labeling a human writer's work as AI-generated is a worse error than missing AI content. A false positive harms a creator's reputation; a false negative leaves content unlabeled. The threshold design reflects this asymmetry:

| Combined Score | Attribution | Confidence |
|---|---|---|
| ≥ 0.75 | `ai_generated` | = ai_score |
| ≤ 0.35 | `human_written` | = 1 − ai_score |
| 0.36 – 0.74 | `uncertain` | 0.5 + distance from midpoint |

The bar for issuing an `ai_generated` verdict is deliberately high. The wide uncertain band is not a failure — it is the system being honest rather than forcing a verdict it does not have confidence in.

---

## Transparency Label Variants

### Variant 1 — High-confidence AI (`ai_generated`, score ≥ 0.75)

```
⚠️ Likely AI-Generated (82% confidence)
Our analysis suggests this content was probably created with an AI writing tool.
This is based on automated signals and may not be accurate.
If you are the creator and believe this is wrong, you can submit an appeal.
```

### Variant 2 — High-confidence human (`human_written`, score ≤ 0.35)

```
✅ Likely Human-Written (79% confidence)
Our analysis suggests this content was written by a person.
No automated system is perfect — this reflects our best assessment, not a guarantee.
```

### Variant 3 — Uncertain (score 0.36–0.74)

```
🔍 Origin Unclear
We were unable to confidently determine whether this content was written by a human
or generated by AI. It shows characteristics of both.
Treat this content as you would any unverified source.
```

**Design notes:**
- The uncertain label gives no confidence percentage — "51% confidence" would sound nearly certain but is nearly random.
- The AI label always includes an appeal path, because a false positive is the worst outcome.
- The human label includes an epistemic caveat — this is an assessment, not a guarantee.

---

## Appeals Workflow

**Who can appeal:** Any party may submit an appeal, not only a verified original creator. This is intentional — content is sometimes submitted on behalf of someone else, attributed to deceased or anonymous writers, or shared by a platform on a creator's behalf. The system does not gate appeals on identity verification; it trusts the reasoning provided and asks the `creator_id` field to be filled in for record-keeping, not authentication. The tradeoff is that this system does not prevent a bad-faith third party from appealing on someone else's behalf — that risk is accepted in favor of accessibility.

**What information is provided:** A `creator_id` (identifying who is submitting the appeal, not necessarily the original author) and a `reasoning` field explaining why the classification is believed to be wrong.

A creator who disputes a classification submits `POST /appeal/<content_id>` with this information. The system:

1. Validates the content ID exists
2. Checks no appeal is already pending
3. Records the creator's reasoning alongside the original decision and confidence score
4. Sets the content status to `under_review`
5. Writes a structured entry to the audit log
6. Returns confirmation to the creator

**What a human reviewer sees in the appeal queue:** Querying `GET /status/<content_id>` for an under-review item surfaces the original attribution and confidence score, the signal breakdown (lexical and LLM scores individually, plus the LLM's stated reasoning), the appeal status, and the appellant's submitted reasoning. This gives the reviewer both the system's original justification and the creator's counter-argument side by side.

**Automated re-classification is not triggered.** Running the same signals on the same text produces the same result. A human moderator needs context the system cannot see — drafts, revision history, the creator's track record. Automated re-classification would also create a gaming surface where creators submit appeals until they receive a favorable result.

### Anticipated edge cases

**Edge case 1 — Bad faith appeal.** A creator appeals content that was genuinely AI-generated. The system does not attempt to detect this. The appeal is logged, the status is set to `under_review`, and a human moderator evaluates it with full context. The system's job is to capture the appeal honestly, not to adjudicate it.

**Edge case 2 — Idioms and common phrases.** A human writer whose work relies heavily on classic idioms, proverbs, or well-known sayings may be flagged by both signals — the lexical signal because familiar phrases have predictable structure, the LLM signal because those phrases appear frequently in AI training data. This creator has a legitimate appeal. The confidence score should reflect the ambiguity; if the combined score falls in the uncertain band, no verdict is issued. If it crosses the AI threshold, the appeal process is the appropriate remedy.

---

## AI Tool Plan

### M3 — Submission endpoint + first signal

**Inputs provided to the AI tool:** The Detection Signals section (lexical signal description only) and the Architecture Diagram above, focused on the submission flow up through Signal 1.

**What I'll ask for:** A Flask app skeleton with the `POST /submit` route, request validation, and the lexical signal function (`compute_lexical_signal`) implementing sentence length variance, TTR, punctuation ratio, and hedge word density.

**How I'll verify:** Before wiring the signal into the endpoint, I'll test it directly against three hand-picked samples: a few lines from a Maya Angelou poem (known human, literary), a paragraph generated by asking ChatGPT to write on a similar topic (known AI), and a piece I write myself specifically designed as an edge case (e.g., deliberately uniform sentence structure). I'll check that the function runs without errors on all three and returns a score between 0 and 1, and I'll inspect whether the relative ordering of scores makes intuitive sense before trusting the function.

---

### M4 — Second signal + confidence scoring

**Inputs provided to the AI tool:** The full Detection Signals section (both signals), the Confidence Scoring & Thresholds section, and the Architecture Diagram, focused on the signal-combination and threshold-check stages.

**What I'll ask for:** The LLM signal function (`compute_llm_signal`) using the Groq API with structured JSON output, plus the `combine_signals` function implementing the weighted formula and threshold logic.

**How I'll verify:** I'll run the same three M3 test samples (Maya Angelou excerpt, ChatGPT-generated paragraph, my own edge-case sample) through the full combined pipeline. I expect the human-written sample to score low (toward `human_written`) and the ChatGPT sample to score high (toward `ai_generated`). If the two come back nearly identical, or if the edge case doesn't land in the uncertain band as expected, that tells me the weighting or thresholds need adjustment before moving on.

---

### M5 — Production layer (labels + appeals)

**Inputs provided to the AI tool:** The Transparency Label Variants section and the Appeals Workflow section (including both edge cases), plus the Architecture Diagram's appeal flow.

**What I'll ask for:** The label generation function producing all three exact label variants, and the `POST /appeal/<content_id>` and `GET /status/<content_id>` routes.

**How I'll verify:** For labels, I'll force each of the three score ranges (≥0.75, ≤0.35, and the uncertain band) through the generator and confirm the output text matches the exact variants defined in this document. For appeals, I'll run a concrete request sequence: (1) submit a piece of content via `POST /submit` and record the returned `content_id`; (2) call `POST /appeal/<content_id>` with a `creator_id` and `reasoning`; (3) confirm the appeal response shows status `under_review`; (4) call `GET /status/<content_id>` and confirm the status is `under_review` and the `appeal.reasoning` field is populated with what I submitted.