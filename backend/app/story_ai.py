"""Local-AI story generation for the reading library.

Calls a locally-hosted Ollama server (no cloud API, no API key) to write a
short English story matched to a CEFR level and a theme the administrator
describes. The admin reviews and edits the result before it is saved.
"""

from __future__ import annotations

import json
import os
import re

import requests

OLLAMA_HOST = (os.getenv("OLLAMA_HOST") or "http://ollama:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL") or "llama3.2:3b"
OLLAMA_TIMEOUT = 120
MAX_ATTEMPTS = 3

# (minimum words, target words, grammar/vocabulary guidance) per CEFR level.
# Small local models tend to undershoot the requested length, so a single
# target number (repeated forcefully in the prompt) works better than a
# range, and generation is retried with stronger wording if it falls short.
LEVEL_SPECS = {
    "A1": (60, 90, "Only the present simple tense. Very common everyday words. "
                    "Short sentences of 5 to 8 words."),
    "A2": (90, 130, "Present and past simple tense. Common vocabulary and simple "
                     "connectors such as and, but, because."),
    "B1": (130, 180, "A mix of past, present and future tenses. Everyday vocabulary "
                       "with a few less common words."),
    "B2": (180, 250, "Varied tenses and some complex sentences. A few idiomatic "
                       "expressions."),
    "C1": (250, 320, "Advanced vocabulary, complex sentence structures, natural "
                       "idiomatic language."),
    "C2": (320, 400, "Native-like complexity, sophisticated vocabulary, nuanced "
                       "structures."),
}


class StoryGenerationError(RuntimeError):
    """Raised when the local AI could not produce a usable story."""


def _json_unescape(text: str) -> str:
    return (
        text.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\t", " ")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
    )


def _extract_fields_fallback(raw_text: str) -> dict | None:
    """Best-effort field extraction for JSON truncated mid-generation.

    A local model can hit its token limit before closing the JSON object,
    especially for longer stories. Rather than discard a mostly-complete
    story, pull the title/story fields out with a regex tolerant of a
    missing closing quote/brace at the very end.
    """
    title_match = re.search(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_text, re.DOTALL)
    story_match = re.search(r'"story"\s*:\s*"((?:[^"\\]|\\.)*)', raw_text, re.DOTALL)
    if not title_match or not story_match:
        return None

    title = _json_unescape(title_match.group(1)).strip()
    story = _json_unescape(story_match.group(1)).strip().rstrip("\\").strip()
    if not title or not story:
        return None
    return {"title": title, "story": story}


def _build_prompt(theme: str, level_code: str, target_words: int, guidance: str, retry_note: str = "") -> str:
    return (
        "You are an English teacher who writes short stories for language learners.\n"
        f"Target level: CEFR {level_code}.\n"
        f"Grammar and vocabulary rules for this level: {guidance}\n"
        f"Topic requested by the teacher: {theme}\n\n"
        f"The story MUST be at least {target_words} words long. This is a hard "
        "requirement: keep adding events, dialogue, descriptions or extra scenes "
        f"until you reach at least {target_words} words. A story shorter than "
        "that is not acceptable.\n"
        f"{retry_note}"
        "Write the story in English only. Respond with ONLY a JSON object with two keys: "
        '"title" (a short English title, at most 8 words) and "story" (the full story as '
        "plain paragraphs, no markdown, no headers, no bullet points, no title repeated "
        "inside the story)."
    )


def _call_ollama(prompt: str) -> dict:
    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.8, "num_predict": 2048},
            },
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise StoryGenerationError(
            "Could not reach the local AI engine (Ollama). Make sure the "
            "'ollama' service is running and the model has finished downloading."
        ) from exc

    try:
        payload = response.json()
        raw_text = payload.get("response", "")
    except (ValueError, AttributeError) as exc:
        raise StoryGenerationError("The local AI returned an unreadable response.") from exc

    try:
        data = json.loads(raw_text)
        title = str(data.get("title") or "").strip()
        story = str(data.get("story") or "").strip()
    except (json.JSONDecodeError, AttributeError):
        fallback = _extract_fields_fallback(raw_text)
        if not fallback:
            raise StoryGenerationError(
                "The local AI response could not be parsed as a story. Try again."
            )
        title, story = fallback["title"], fallback["story"]

    if not title or not story:
        raise StoryGenerationError("The local AI did not return a complete story. Try again.")

    return {"title": title, "story": story}


def generate_story(theme: str, level_code: str) -> dict:
    """Return {"title": str, "story": str} generated by the local Ollama model.

    Retries with a stronger prompt if the model undershoots the target word
    count (common with small local models), keeping the longest attempt.
    """
    theme = (theme or "").strip()
    level_code = (level_code or "A1").strip().upper()

    if not theme:
        raise StoryGenerationError("Describe what the story should be about first.")
    if len(theme) > 300:
        raise StoryGenerationError("Keep the story description under 300 characters.")

    min_words, target_words, guidance = LEVEL_SPECS.get(level_code, LEVEL_SPECS["A1"])

    best = None
    best_word_count = -1
    retry_note = ""

    for attempt in range(1, MAX_ATTEMPTS + 1):
        prompt = _build_prompt(theme, level_code, target_words, guidance, retry_note)
        result = _call_ollama(prompt)
        word_count = len(result["story"].split())

        if word_count > best_word_count:
            best = result
            best_word_count = word_count

        if word_count >= min_words:
            return result

        retry_note = (
            f"Your previous attempt only had {word_count} words, which is too "
            f"short. Write a longer, more detailed story of at least {target_words} "
            "words this time.\n"
        )

    return best
