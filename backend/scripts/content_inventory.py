#!/usr/bin/env python3
"""Generate a human-readable inventory of all curriculum and assessment JSON files."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"


def load(path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def count_questions(data):
    return len(data.get("questions", []) or []) + sum(
        len(p.get("questions", []) or [])
        for p in data.get("passages", []) or []
    )


print("ENGLISH PRACTICE HUB - CONTENT INVENTORY")
print("=" * 72)

grand_questions = 0
grand_topics = 0
grand_passages = 0

for path in sorted((CONTENT / "curriculum").glob("*.json")):
    data = load(path)
    level = data.get("level", {})
    topics = data.get("topics", [])
    q_count = 0
    p_count = 0
    skills = Counter()

    for topic in topics:
        p_count += len(topic.get("passages", []) or [])
        for q in topic.get("questions", []) or []:
            q_count += 1
            skills[q.get("skill", "?")] += 1
        for passage in topic.get("passages", []) or []:
            for q in passage.get("questions", []) or []:
                q_count += 1
                skills[q.get("skill", "?")] += 1

    grand_topics += len(topics)
    grand_questions += q_count
    grand_passages += p_count

    print(f"{level.get('code','?'):>2}  topics={len(topics):>2}  questions={q_count:>3}  passages={p_count:>2}  {path.name}")

print("-" * 72)
print("ASSESSMENTS")

assessment_questions = 0
for path in sorted((CONTENT / "assessments").glob("*.json")):
    data = load(path)
    meta = data.get("assessment", {})
    q_count = count_questions(data)
    p_count = len(data.get("passages", []) or [])
    assessment_questions += q_count
    print(f"{meta.get('code','?'):<34} q={q_count:>3}  passages={p_count:>2}")

print("-" * 72)
print(f"Curriculum topics:       {grand_topics}")
print(f"Curriculum questions:    {grand_questions}")
print(f"Curriculum passages:     {grand_passages}")
print(f"Assessment questions:    {assessment_questions}")
print(f"Total question bank:     {grand_questions + assessment_questions}")
