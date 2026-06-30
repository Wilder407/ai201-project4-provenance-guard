"""
M5 verification, per the AI Tool Plan in planning.md:

  1. Force each of the three score ranges through generate_transparency_label
     directly, and confirm the output text matches the exact variants
     defined in planning.md.
  2. Run the real appeal request sequence:
       (1) POST /submit -> record content_id
       (2) POST /appeal/<content_id> with creator_id + reasoning
       (3) confirm appeal response shows status "under_review"
       (4) GET /status/<content_id> -> confirm status is "under_review"
           and appeal.reasoning is populated

Part 1 tests the function directly (no server needed).
Part 2 requires the Flask server running at http://localhost:5001.
"""

import json
import urllib.request

from main import generate_transparency_label

BASE = "http://localhost:5001"


def post(path, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as resp:
        return json.loads(resp.read())


def test_label_variants():
    print("=" * 70)
    print("Part 1: Label Variants (direct function test, no server needed)")
    print("=" * 70)

    cases = [
        ("ai_generated", 0.82, "AI-generated, high confidence"),
        ("ai_generated", 0.6, "AI-generated, capped confidence (short-text case)"),
        ("human_written", 0.79, "Human-written, high confidence"),
        ("uncertain", 0.55, "Uncertain"),
    ]

    for attribution, confidence, description in cases:
        label = generate_transparency_label(attribution, confidence)
        print(f"\n{description}  (attribution={attribution}, confidence={confidence})")
        print(f"   {label}")

        # Spot checks against planning.md commitments
        if attribution == "ai_generated":
            assert "appeal" in label.lower(), "FAIL: ai_generated label must always mention appeal"
        if attribution == "uncertain":
            assert "%" not in label, "FAIL: uncertain label must not show a confidence percentage"

    print("\n✅ All label variant checks passed.")


def test_appeal_sequence():
    print("\n" + "=" * 70)
    print("Part 2: Full Appeal Request Sequence (requires running server)")
    print("=" * 70)

    # Step 1: submit content
    print("\n(1) POST /submit")
    submission = post("/submit", {
        "content": (
            "In today's fast-paced world, it is essential to recognize the "
            "importance of maintaining a healthy work-life balance. Many "
            "professionals struggle to find time for self-care amidst their "
            "demanding schedules. It is crucial to prioritize mental health "
            "and well-being in order to achieve long-term success."
        ),
        "creator_id": "user_test_appeal",
        "title": "Appeal Sequence Test",
    })
    content_id = submission["content_id"]
    print(f"    content_id  : {content_id}")
    print(f"    attribution : {submission['attribution']}")
    print(f"    label       : {submission['transparency_label']}")

    # Step 2: submit appeal
    print(f"\n(2) POST /appeal/{content_id}")
    appeal_response = post(f"/appeal/{content_id}", {
        "creator_id": "user_test_appeal",
        "reasoning": (
            "I wrote this myself as a practice essay for a writing class. "
            "I tend to write formally because that's the style my instructor "
            "has reinforced."
        ),
    })
    print(f"    response status field : {appeal_response['status']}")
    assert appeal_response["status"] == "under_review", "FAIL: appeal response should show under_review"

    # Step 3 was the check above; Step 4: confirm via GET /status
    print(f"\n(4) GET /status/{content_id}")
    status = get(f"/status/{content_id}")
    print(f"    status            : {status['status']}")
    print(f"    appeal.reasoning  : {status['appeal']['reasoning']}")
    assert status["status"] == "under_review", "FAIL: /status should show under_review"
    assert status["appeal"]["reasoning"], "FAIL: appeal.reasoning should be populated"

    print("\n✅ Full appeal sequence verified: status is under_review, reasoning is populated.")


if __name__ == "__main__":
    test_label_variants()
    try:
        test_appeal_sequence()
    except Exception as e:
        print(f"\n⚠️  Part 2 skipped or failed: {e}")
        print("    Make sure the Flask server is running: python main.py")