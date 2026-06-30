"""
M4 verification (updated): run all three samples through the full pipeline,
now including the short-text confidence cap safeguard.

Specific thing being tested: does 'my_edge_case_uniform' (47 words, under
the 60-word threshold) still get labeled ai_generated, but now with
confidence capped at 0.6 instead of the original 0.89?
"""

import re
from main import compute_lexical_signal, compute_llm_signal, combine_signals

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
    print("=" * 70)
    print("M4 -- Full Pipeline Test WITH Short-Text Safeguard")
    print("=" * 70)

    for name, text in SAMPLES.items():
        lexical = compute_lexical_signal(text)
        llm = compute_llm_signal(text)
        word_count = len(re.findall(r'\b\w+\b', text))
        attribution, confidence = combine_signals(lexical, llm, word_count)

        print(f"\n{name}:")
        print(f"   word count    : {word_count}")
        print(f"   lexical score : {lexical['score']}")
        print(f"   llm score     : {llm['score']}")
        print(f"   ATTRIBUTION   : {attribution}")
        print(f"   CONFIDENCE    : {confidence}")

    print("\n" + "-" * 70)
    print("Expected: my_edge_case_uniform should still be ai_generated,")
    print("but confidence should now be capped at 0.6 (was 0.89 before fix).")

if __name__ == "__main__":
    run()