"""Server-side text-to-speech.

Listening exercises used to rely on the browser's Web Speech API, which only
speaks with voices the visitor's operating system happens to have installed.
Devices without an English language pack could not play audio at all (or, in
some browsers, silently fell back to a Spanish voice).

To make listening work identically for every student regardless of device,
audio is generated here, once per distinct (text, accent, rate) combination,
and streamed to the browser as an MP3 file. Results are cached on disk so a
question or passage that has already been played does not hit the network
again.
"""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request
from flask_login import login_required
from gtts import gTTS
from gtts.tts import gTTSError

tts_bp = Blueprint("tts", __name__, url_prefix="/tts")

CACHE_DIR = Path(tempfile.gettempdir()) / "english_practice_hub_tts_cache"

MAX_TEXT_LENGTH = 5000
MIN_RATE = 0.5
MAX_RATE = 2.0

# gTTS speaks English with a single voice per Google top-level domain. This
# maps the accent codes already stored on questions/passages to the closest
# available domain instead of requiring a specific OS voice to exist.
ACCENT_TLD = {
    "en-us": "com",
    "en-gb": "co.uk",
    "en-au": "com.au",
    "en-ca": "ca",
    "en-in": "co.in",
    "en-ie": "ie",
    "en-za": "co.za",
}


class TTSError(RuntimeError):
    """Raised when speech audio could not be generated."""


def _tld_for_accent(accent: str) -> str:
    return ACCENT_TLD.get((accent or "en-us").strip().lower(), "com")


def _clamp_rate(rate: float) -> float:
    try:
        rate = float(rate)
    except (TypeError, ValueError):
        rate = 1.0
    return max(MIN_RATE, min(MAX_RATE, rate))


def _cache_path(text: str, accent: str, rate: float) -> Path:
    key = f"{accent.lower()}|{rate:.2f}|{text}".encode("utf-8")
    digest = hashlib.sha256(key).hexdigest()
    return CACHE_DIR / f"{digest}.mp3"


def _adjust_tempo(mp3_bytes: bytes, rate: float) -> bytes:
    """Speed up or slow down audio without changing its pitch, via ffmpeg."""
    if abs(rate - 1.0) < 0.01:
        return mp3_bytes

    with tempfile.TemporaryDirectory() as tmp_dir:
        src = Path(tmp_dir) / "in.mp3"
        dst = Path(tmp_dir) / "out.mp3"
        src.write_bytes(mp3_bytes)

        result = subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(src),
                "-filter:a", f"atempo={rate}",
                str(dst),
            ],
            capture_output=True,
            timeout=30,
        )

        if result.returncode != 0 or not dst.exists():
            raise TTSError(
                "ffmpeg could not adjust playback speed: "
                + result.stderr.decode("utf-8", errors="ignore")[:300]
            )

        return dst.read_bytes()


def synthesize_speech(text: str, accent: str = "en-US", rate: float = 1.0) -> bytes:
    """Return MP3 audio bytes for ``text``, generating and caching it if needed."""
    text = (text or "").strip()
    if not text:
        raise TTSError("No text was provided.")

    rate = _clamp_rate(rate)
    cache_file = _cache_path(text, accent, rate)

    try:
        if cache_file.exists():
            return cache_file.read_bytes()
    except OSError:
        pass

    try:
        buffer = BytesIO()
        gTTS(text=text, lang="en", tld=_tld_for_accent(accent)).write_to_fp(buffer)
        audio = buffer.getvalue()
    except gTTSError as exc:
        raise TTSError(f"Could not reach the speech service: {exc}") from exc
    except Exception as exc:  # network/parsing failures from the gTTS client
        raise TTSError(f"Could not generate speech: {exc}") from exc

    audio = _adjust_tempo(audio, rate)

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(audio)
    except OSError:
        pass

    return audio


@tts_bp.route("/speak", methods=["POST"])
@login_required
def speak():
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text") or "").strip()
    accent = str(payload.get("lang") or "en-US").strip() or "en-US"

    try:
        rate = float(payload.get("rate") or 1.0)
    except (TypeError, ValueError):
        rate = 1.0

    if not text:
        return jsonify({"error": "No text was provided."}), 400
    if len(text) > MAX_TEXT_LENGTH:
        return jsonify({"error": "Text is too long to synthesize."}), 400

    try:
        audio = synthesize_speech(text, accent=accent, rate=rate)
    except TTSError as exc:
        current_app.logger.warning("TTS generation failed: %s", exc)
        return jsonify({"error": "The audio could not be generated. Please try again."}), 502

    return Response(
        audio,
        mimetype="audio/mpeg",
        headers={"Cache-Control": "private, max-age=86400"},
    )
