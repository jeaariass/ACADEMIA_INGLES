"""Rule-based adaptive engine for CEFR level assessments.

This module deliberately implements a transparent heuristic rather than a
psychometrically calibrated CAT/IRT model. It uses the question field
``level_difficulty`` (1-5, relative to the question's own CEFR level), keeps
section coverage balanced, preserves reading/listening passages as contextual
blocks, and updates a latent 1-5 ability estimate after every answer.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict


ADAPTIVE_TARGET_QUESTIONS = 20
ADAPTIVE_START_ABILITY = 3.0
ADAPTIVE_SECTION_ORDER = [
    "grammar",
    "vocabulary",
    "reading",
    "listening",
    "integrated",
]
ADAPTIVE_SECTION_TARGETS = {
    "grammar": 6,
    "vocabulary": 4,
    "reading": 4,
    "listening": 4,
    "integrated": 2,
}


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def item_difficulty(question) -> int:
    """Return a safe CEFR-relative difficulty value between 1 and 5."""
    value = getattr(question, "level_difficulty", None)
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = 3
    return max(1, min(5, value))


def difficulty_from_ability(ability: float) -> int:
    """Convert continuous ability to an integer target difficulty (half-up)."""
    ability = clamp(float(ability), 1.0, 5.0)
    return max(1, min(5, int(math.floor(ability + 0.5))))


def update_ability(
    ability: float,
    question_difficulty: int,
    is_correct: bool,
    k_factor: float = 0.75,
) -> float:
    """Update ability using a small Elo-like rule.

    The value is intentionally interpretable on the same 1-5 scale as
    ``level_difficulty``. This is a platform heuristic, not an IRT theta score.
    """
    ability = clamp(float(ability), 1.0, 5.0)
    difficulty = float(max(1, min(5, int(question_difficulty))))

    # Expected probability of success. At equal ability/difficulty it is 0.5.
    expected = 1.0 / (1.0 + math.exp((difficulty - ability) * 1.35))
    observed = 1.0 if is_correct else 0.0
    updated = ability + (k_factor * (observed - expected))
    return round(clamp(updated, 1.0, 5.0), 4)


def initial_state() -> dict:
    return {
        "version": 1,
        "target_questions": ADAPTIVE_TARGET_QUESTIONS,
        "start_ability": ADAPTIVE_START_ABILITY,
        "ability": ADAPTIVE_START_ABILITY,
        "history": [],
    }


def bank_summary(assessment) -> dict:
    difficulty_counts = {level: 0 for level in range(1, 6)}
    section_counts = {section: 0 for section in ADAPTIVE_SECTION_ORDER}
    passage_ids = set()

    for link in assessment.question_links:
        difficulty_counts[item_difficulty(link.question)] += 1
        section_counts.setdefault(link.section, 0)
        section_counts[link.section] += 1
        if link.question.passage_id:
            passage_ids.add(link.question.passage_id)

    populated = [key for key, value in difficulty_counts.items() if value]
    return {
        "total": len(assessment.question_links),
        "target_questions": ADAPTIVE_TARGET_QUESTIONS,
        "difficulty_counts": difficulty_counts,
        "section_counts": section_counts,
        "section_targets": dict(ADAPTIVE_SECTION_TARGETS),
        "populated_difficulties": populated,
        "passage_count": len(passage_ids),
        "ready_for_full_adaptation": len(populated) >= 3,
    }


def _stable_key(attempt_id: int, step: int, key: str) -> str:
    raw = f"{attempt_id}:{step}:{key}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _section_fill_ratio(section: str, counts: dict[str, int]) -> float:
    target = ADAPTIVE_SECTION_TARGETS.get(section, 0)
    if target <= 0:
        return float("inf")
    return counts.get(section, 0) / target


def _section_order(section: str) -> int:
    try:
        return ADAPTIVE_SECTION_ORDER.index(section)
    except ValueError:
        return len(ADAPTIVE_SECTION_ORDER)


def _unit_average_difficulty(links) -> float:
    if not links:
        return 3.0
    return sum(item_difficulty(link.question) for link in links) / len(links)


def _build_units(section_links, section: str, remaining_section: int, remaining_total: int):
    """Build selectable units.

    Reading/listening questions that belong to a passage remain grouped so the
    learner receives the context and limited audio playback coherently.
    """
    if not section_links or remaining_total <= 0:
        return []

    limit = max(1, min(remaining_section if remaining_section > 0 else remaining_total, remaining_total))

    if section in {"reading", "listening"}:
        grouped = defaultdict(list)
        standalone = []
        for link in section_links:
            if link.question.passage_id:
                grouped[link.question.passage_id].append(link)
            else:
                standalone.append(link)

        units = []
        for passage_id, links in grouped.items():
            ordered = sorted(links, key=lambda item: (item.sort_order, item.id))
            units.append({
                "section": section,
                "links": ordered[:limit],
                "passage_id": passage_id,
            })
        for link in standalone:
            units.append({"section": section, "links": [link], "passage_id": None})
        return units

    return [
        {"section": section, "links": [link], "passage_id": None}
        for link in section_links
    ]


def choose_next_unit(
    assessment,
    *,
    answered_ids: set[int],
    section_counts: dict[str, int],
    topic_counts: dict[int, int],
    target_difficulty: int,
    attempt_id: int,
    step: int,
    answered_count: int,
) -> dict | None:
    """Choose the next question or contextual passage block.

    Selection priorities:
    1. satisfy section quotas;
    2. use the closest available CEFR-relative difficulty;
    3. avoid overusing the same topic;
    4. use a deterministic per-attempt tie-breaker so refreshes are stable.
    """
    remaining_total = ADAPTIVE_TARGET_QUESTIONS - answered_count
    if remaining_total <= 0:
        return None

    available = [
        link for link in assessment.question_links
        if link.question_id not in answered_ids
    ]
    if not available:
        return None

    by_section = defaultdict(list)
    for link in available:
        by_section[link.section].append(link)

    needed_sections = []
    for section in ADAPTIVE_SECTION_ORDER:
        target = ADAPTIVE_SECTION_TARGETS.get(section, 0)
        current = section_counts.get(section, 0)
        if current < target and by_section.get(section):
            needed_sections.append(section)

    if needed_sections:
        section = min(
            needed_sections,
            key=lambda value: (
                _section_fill_ratio(value, section_counts),
                _section_order(value),
            ),
        )
    else:
        # A section may run out of questions. Redistribute the remaining slots
        # rather than stopping the attempt early.
        section = min(
            by_section.keys(),
            key=lambda value: (
                section_counts.get(value, 0),
                _section_order(value),
            ),
        )

    target_for_section = ADAPTIVE_SECTION_TARGETS.get(section, remaining_total)
    remaining_section = max(0, target_for_section - section_counts.get(section, 0))
    units = _build_units(
        by_section[section],
        section,
        remaining_section,
        remaining_total,
    )
    if not units:
        return None

    def unit_score(unit):
        links = unit["links"]
        avg_difficulty = _unit_average_difficulty(links)
        topic_penalty = sum(topic_counts.get(link.question.topic_id, 0) for link in links) / len(links)
        stable = _stable_key(
            attempt_id,
            step,
            ",".join(str(link.id) for link in links),
        )
        return (
            abs(avg_difficulty - target_difficulty),
            topic_penalty,
            stable,
        )

    selected = min(units, key=unit_score)
    selected["target_difficulty"] = int(target_difficulty)
    selected["average_difficulty"] = round(_unit_average_difficulty(selected["links"]), 2)
    return selected


def answered_context(attempt) -> dict:
    """Derive selection context from persisted answers and assessment links."""
    link_by_question = {
        link.question_id: link
        for link in attempt.assessment.question_links
    }
    answered = [
        answer for answer in attempt.answers
        if answer.selected_option is not None and answer.question_id in link_by_question
    ]

    section_counts = Counter()
    topic_counts = Counter()
    for answer in answered:
        link = link_by_question[answer.question_id]
        section_counts[link.section] += 1
        if answer.question.topic_id:
            topic_counts[answer.question.topic_id] += 1

    return {
        "answers": answered,
        "answered_ids": {answer.question_id for answer in answered},
        "answered_count": len(answered),
        "section_counts": dict(section_counts),
        "topic_counts": dict(topic_counts),
    }


def result_summary(attempt) -> dict:
    profile = dict(attempt.result_profile or {})
    state = dict(profile.get("adaptive_level") or initial_state())
    answers = [answer for answer in attempt.answers if answer.selected_option is not None]
    difficulties = [item_difficulty(answer.question) for answer in answers]
    history = list(state.get("history") or [])

    average = round(sum(difficulties) / len(difficulties), 2) if difficulties else 0.0
    return {
        "target_questions": int(state.get("target_questions", ADAPTIVE_TARGET_QUESTIONS)),
        "start_ability": float(state.get("start_ability", ADAPTIVE_START_ABILITY)),
        "ending_ability": round(float(state.get("ability", ADAPTIVE_START_ABILITY)), 2),
        "ending_target_difficulty": difficulty_from_ability(
            float(state.get("ability", ADAPTIVE_START_ABILITY))
        ),
        "average_item_difficulty": average,
        "minimum_item_difficulty": min(difficulties) if difficulties else None,
        "maximum_item_difficulty": max(difficulties) if difficulties else None,
        "units_completed": len(history),
        "history": history,
    }
