"""Runs the study protocol's required boundary-case check against a live server:
20 queries spanning IN SCOPE and OUT OF SCOPE per the leaflet corpus scope rules
(see docs/STUDY_PROTOCOL_NOTES.md / Section 8 of the experiment plan PDF).

Usage: python tests/boundary_cases.py [base_url] [product_slug]
Requires a running server with the corpus already ingested for the given product.
"""
import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
PRODUCT_SLUG = sys.argv[2] if len(sys.argv) > 2 else "paracetamol"

from app.rag.boundary_cases import CASES  # noqa: E402


def main() -> None:
    session_resp = requests.post(
        f"{BASE_URL}/api/session/start",
        json={
            "platform": "desktop_web",
            "product_slug": PRODUCT_SLUG,
            "device_info": {"user_agent": "boundary-test", "screen_width": 1024, "screen_height": 768},
        },
    )
    session_resp.raise_for_status()
    session_id = session_resp.json()["session_id"]

    correct = 0
    for query, expected in CASES:
        resp = requests.post(f"{BASE_URL}/api/query", json={
            "session_id": session_id, "query_text": query, "input_method": "typed",
        })
        resp.raise_for_status()
        data = resp.json()
        ok = data["in_scope"] == expected
        correct += ok
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] expected={expected!s:5} got={data['in_scope']!s:5} | {query}")
        if not ok:
            print(f"       -> {data['answer_text']}")

    print(f"\n{correct}/{len(CASES)} correct")
    requests.post(f"{BASE_URL}/api/session/{session_id}/end", json={"errors_logged": 0})


if __name__ == "__main__":
    main()
