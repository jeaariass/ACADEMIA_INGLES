"""Small dependency-free smoke test for the Phase 2 adaptive selection engine."""

from pathlib import Path
import importlib.util

MODULE = Path(__file__).resolve().parents[1] / "app" / "adaptive_level.py"
spec = importlib.util.spec_from_file_location("adaptive_level", MODULE)
adaptive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adaptive)


class Passage:
    def __init__(self, pid):
        self.id = pid


class Question:
    def __init__(self, qid, topic_id, difficulty, passage_id=None):
        self.id = qid
        self.topic_id = topic_id
        self.level_difficulty = difficulty
        self.passage_id = passage_id
        self.passage = Passage(passage_id) if passage_id else None


class Link:
    def __init__(self, lid, qid, section, topic_id, difficulty, passage_id=None, order=0):
        self.id = lid
        self.question_id = qid
        self.section = section
        self.sort_order = order
        self.question = Question(qid, topic_id, difficulty, passage_id)


class Assessment:
    def __init__(self, links):
        self.question_links = links


def build_bank():
    links = []
    lid = 1
    qid = 1
    section_specs = [
        ("grammar", 12),
        ("vocabulary", 8),
        ("integrated", 4),
    ]
    for section, count in section_specs:
        for i in range(count):
            links.append(Link(lid, qid, section, (i % 6) + 1, (i % 5) + 1, order=i))
            lid += 1
            qid += 1

    for section in ("reading", "listening"):
        for passage_index in range(2):
            pid = 1000 + lid
            for i in range(4):
                links.append(Link(lid, qid, section, passage_index + 20, (i % 5) + 1, pid, i))
                lid += 1
                qid += 1
    return Assessment(links)


def main():
    ability = 3.0
    ability_after_two_correct = adaptive.update_ability(
        adaptive.update_ability(ability, 3, True), 3, True
    )
    assert ability_after_two_correct > ability
    assert adaptive.difficulty_from_ability(ability_after_two_correct) >= 4

    assessment = build_bank()
    unit = adaptive.choose_next_unit(
        assessment,
        answered_ids=set(),
        section_counts={},
        topic_counts={},
        target_difficulty=3,
        attempt_id=10,
        step=0,
        answered_count=0,
    )
    assert unit is not None
    assert unit["section"] == "grammar"
    assert len(unit["links"]) == 1

    # Once grammar/vocabulary are partially filled, reading should be returned
    # as a contextual passage block rather than isolated questions.
    unit = adaptive.choose_next_unit(
        assessment,
        answered_ids=set(),
        section_counts={"grammar": 2, "vocabulary": 1},
        topic_counts={},
        target_difficulty=3,
        attempt_id=11,
        step=3,
        answered_count=3,
    )
    assert unit is not None
    assert unit["section"] == "reading"
    assert len(unit["links"]) == 4
    assert len({link.question.passage_id for link in unit["links"]}) == 1

    print("Adaptive engine smoke test: OK")


if __name__ == "__main__":
    main()
