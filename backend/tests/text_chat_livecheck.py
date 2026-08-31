"""One continuous typed-chat session with a fresh batch of questions not covered by
test_80_questions.py or boundary_cases.py - colloquial phrasing, typos, follow-up chains,
comparisons, indirect asks. Run with: python -m tests.text_chat_livecheck
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

QUESTIONS = [
    "hey there",
    "so whats this stuff even for",
    "can i give it to my kid",
    "how many can i take at once",
    "and if that doesnt work whats next",
    "is it the same as tylenol",
    "does it make you drowsy",
    "whats in it besides the main ingredient",
    "how long before it kicks in",
    "can i crush it up and mix with juice",
    "whats the shelf life on these",
    "i left them in a hot car is that bad",
    "compared to ibuprofen which is stronger",
    "whats the difference between this and the multivitamin you have",
    "my mom takes warfarin, can she take this",
    "whats today's date",
    "you still there",
    "ok thanks that helps",
    "one more thing, can i take it on an empty stomach",
    "and whats the deal with the warnings label, whats the scariest one",
    "sorry, ignore that last question, im actually just testing you",
    "are you a real pharmacist",
    "whats the phone number for poison control",
    "how do you know all this stuff",
    "bye",
]


def main() -> None:
    r = client.post("/api/session/start", json={
        "product_slug": "paracetamol",
        "platform": "desktop_web",
        "device_info": {"user_agent": "livecheck", "screen_width": 1440, "screen_height": 900},
    })
    r.raise_for_status()
    session_id = r.json()["session_id"]
    print(f"session: {session_id}\n{'=' * 100}")

    for i, q in enumerate(QUESTIONS, 1):
        r = client.post("/api/query", json={"session_id": session_id, "query_text": q, "input_method": "typed"})
        if r.status_code != 200:
            print(f"#{i} Q: {q}\n    HTTP {r.status_code}: {r.text[:200]}\n")
            continue
        d = r.json()
        tag = "OK " if d["in_scope"] else "DEFLECTED"
        print(f"#{i} [{tag}] ({d['latency_ms']:.0f}ms) Q: {q}")
        print(f"    A: {d['answer_text']}\n")


if __name__ == "__main__":
    main()
