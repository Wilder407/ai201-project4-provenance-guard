"""
M3 verification: test compute_lexical_signal() directly, BEFORE wiring it
into the endpoint — per the AI Tool Plan in planning.md.

Three samples:
  1. Maya Angelou excerpt (known human, literary)
  2. ChatGPT-generated paragraph (known AI)
  3. Hand-written edge case (deliberately uniform sentence structure)

Expected per planning.md M3 verification: scores should run without error,
return a value between 0 and 1, and the relative ordering should make
intuitive sense (human sample lower, AI sample higher) before trusting
the function enough to wire it into /submit.
"""

from main import compute_lexical_signal

SAMPLES = {
    "maya_angelou_excerpt": (
        "You may write me down in history with your bitter, twisted lies. "
        "You may trod me in the very dirt, but still, like dust, I'll rise. "
        "Does my sassiness upset you? Why are you beset with gloom? "
        "'Cause I walk like I've got oil wells pumping in my living room."
    ),
    "chatgpt_generated": (
        "In today's fast-paced world, it is essential to recognize the "
        "importance of maintaining a healthy work-life balance. Many "
        "professionals struggle to find time for self-care amidst their "
        "demanding schedules. It is crucial to prioritize mental health "
        "and well-being in order to achieve long-term success and "
        "fulfillment. By implementing effective time management strategies, "
        "individuals can create space for both professional growth and "
        "personal rejuvenation."
    ),
    "my_edge_case_uniform": (
        "The meeting starts at nine o'clock. The agenda has five items. "
        "The first item covers budget review. The second item covers staff "
        "updates. The third item covers project timelines. The fourth item "
        "covers client feedback. The fifth item covers next steps."
    ),
}


def run():
    print("=" * 60)
    print("M3 — Lexical Signal Direct Test")
    print("=" * 60)

    results = {}
    for name, text in SAMPLES.items():
        result = compute_lexical_signal(text)
        results[name] = result["score"]
        print(f"\n{name}:")
        for k, v in result.items():
            print(f"   {k}: {v}")

    print("\n" + "-" * 60)
    print("Sanity checks:")
    print(f"  All scores in [0,1]: {all(0.0 <= v <= 1.0 for v in results.values())}")
    print(f"  Angelou (human) score : {results['maya_angelou_excerpt']}")
    print(f"  ChatGPT (AI) score    : {results['chatgpt_generated']}")
    print(f"  Edge case score       : {results['my_edge_case_uniform']}")
    print("\nNote: my_edge_case_uniform was written with deliberately uniform")
    print("sentence length to test whether the heuristic alone (no LLM signal")
    print("yet) over-flags disciplined-but-human writing as AI — this is the")
    print("documented blind spot from planning.md, expect a HIGHER score here.")


if __name__ == "__main__":
    run()