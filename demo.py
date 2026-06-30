"""
Demo/test script — generates sample audit log entries for README documentation.
Run after starting the server: python demo.py
"""

import json
import urllib.request
import urllib.error

BASE = "http://localhost:5001"

SAMPLES = [
    {
        "label": "Likely Human",
        "title": "Late Night Thoughts",
        "creator_id": "user_hannah_k",
        "content": (
            "i keep meaning to write something real here but every time i sit down "
            "the words just... don't come? it's like 2am and i've been staring at "
            "this blank page for probably forty minutes. maybe longer. "
            "my roommate's still up, i can hear her laughing at something through "
            "the wall, and it's weirdly comforting. anyway. "
            "i've been thinking about what my dad said at dinner last week — "
            "not the words exactly, more the way he looked when he said them. "
            "tired in a way i don't think i've ever been. "
            "is that what growing up is? recognizing tiredness in people you thought "
            "were just... permanent?\n\n"
            "my coffee's gone cold. i made it like an hour ago. "
            "classic. gonna go heat it up and pretend i'll start writing after that."
        ),
    },
    {
        "label": "Likely AI",
        "title": "The Beauty of Perseverance",
        "creator_id": "user_anonymous_7",
        "content": (
            "In the journey of life, perseverance stands as one of the most admirable "
            "qualities a person can possess. It is through the consistent application "
            "of effort and determination that individuals are able to overcome the "
            "inevitable obstacles that arise on the path to success. "
            "Consider the story of Thomas Edison, who famously stated that genius is "
            "one percent inspiration and ninety-nine percent perspiration. "
            "This timeless wisdom reminds us that achievement is not merely the "
            "product of talent, but rather the result of sustained dedication and "
            "unwavering commitment to one's goals. "
            "Furthermore, in examining the biographies of countless successful "
            "individuals throughout history, we consistently find that the common "
            "thread linking their accomplishments is precisely this quality of "
            "perseverance. They did not allow temporary setbacks to define their "
            "ultimate trajectory. Instead, they embraced challenges as opportunities "
            "for growth and learning, emerging from each experience with greater "
            "wisdom and resilience."
        ),
    },
    {
        "label": "Uncertain",
        "title": "Field Notes — October",
        "creator_id": "user_birdwatch_42",
        "content": (
            "October 14th. The marsh is different today — quieter, somehow, even "
            "though there are more birds. Sixteen coots along the eastern edge. "
            "A pair of teals I haven't seen here before.\n\n"
            "I've been coming to this spot every Saturday for three years. "
            "The light changes, the water levels change, but something about the "
            "quality of attention it requires from me stays constant. "
            "You have to be slow. You have to be willing to see nothing for a long time.\n\n"
            "This morning I arrived at 6:15 and sat until almost nine. "
            "The mist burned off around seven-thirty. I didn't write anything down "
            "for the first hour — just watched. I'm not sure what I was waiting for."
        ),
    },
]


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


def run_demo():
    print("=" * 60)
    print("Provenance Guard — Demo Run")
    print("=" * 60)

    ids = []
    for sample in SAMPLES:
        print(f"\n📤 Submitting: '{sample['title']}' (expected: {sample['label']})")
        data = post("/submit", {
            "content": sample["content"],
            "creator_id": sample["creator_id"],
            "title": sample["title"],
        })
        ids.append(data["content_id"])
        print(f"   content_id  : {data['content_id']}")
        print(f"   attribution : {data['attribution']}")
        print(f"   confidence  : {data['confidence']}")
        print(f"   lex score   : {data['signals']['lexical']['score']}")
        print(f"   llm score   : {data['signals']['llm_classifier']['score']}")
        print(f"\n   📋 Label:\n   {data['transparency_label']}")

    # Appeal the AI-labeled submission
    ai_id = ids[1]
    print(f"\n📣 Submitting appeal for content_id: {ai_id}")
    appeal = post(f"/appeal/{ai_id}", {
        "creator_id": "user_anonymous_7",
        "reasoning": (
            "I wrote this essay myself as a school assignment. I write formally "
            "because that's what my English teacher has reinforced. The Edison quote "
            "is something I've known since middle school. I have handwritten drafts "
            "and revision notes I can provide to a moderator."
        ),
    })
    print(f"   status: {appeal['status']}")

    print("\n📚 Audit Log (last 5 entries):")
    log = get("/log?limit=5")
    for entry in log["entries"]:
        print(f"   {json.dumps(entry)}")

    print("\n✅ Demo complete.")


if __name__ == "__main__":
    run_demo()