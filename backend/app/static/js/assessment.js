/*
 * Formal assessment audio.
 *
 * The server controls the play count, but we first verify that an actual
 * English TTS voice exists. This prevents:
 *   1. Spanish-voice fallback.
 *   2. Consuming a permitted play when the device has no English voice.
 */

async function resolveAssessmentEnglishVoice(lang = 'en-US') {
  if (!('speechSynthesis' in window)) return null;

  if (typeof getPreferredVoiceAsync === 'function') {
    return await getPreferredVoiceAsync(lang);
  }

  // Defensive fallback in case speech.js has not loaded for some reason.
  const normalize = (value) => String(value || '')
    .trim()
    .replace(/_/g, '-')
    .toLowerCase();

  const isEnglish = (voice) => {
    const code = normalize(voice && voice.lang);
    return code === 'en' || code.startsWith('en-');
  };

  let voices = window.speechSynthesis.getVoices() || [];

  if (!voices.length) {
    await new Promise((resolve) => {
      const timeout = window.setTimeout(resolve, 2500);

      const handler = () => {
        voices = window.speechSynthesis.getVoices() || [];
        if (voices.length) {
          window.clearTimeout(timeout);

          if (typeof window.speechSynthesis.removeEventListener === 'function') {
            window.speechSynthesis.removeEventListener(
              'voiceschanged',
              handler
            );
          }

          resolve();
        }
      };

      if (typeof window.speechSynthesis.addEventListener === 'function') {
        window.speechSynthesis.addEventListener(
          'voiceschanged',
          handler
        );
      }

      window.speechSynthesis.getVoices();
    });

    voices = window.speechSynthesis.getVoices() || [];
  }

  const target = normalize(lang);

  const english = voices
    .filter(isEnglish)
    .sort((a, b) => {
      const aLang = normalize(a.lang);
      const bLang = normalize(b.lang);

      const aExact = aLang === target ? 1 : 0;
      const bExact = bLang === target ? 1 : 0;

      return bExact - aExact;
    });

  return english[0] || null;
}

function assessmentEnglishVoiceError() {
  if (typeof notifyEnglishVoiceUnavailable === 'function') {
    notifyEnglishVoiceUnavailable();
    return;
  }

  alert(
    'No English text-to-speech voice is available on this device. ' +
    'Please enable or install an English voice and reload the page.'
  );
}

async function playAssessmentAudio(button) {
  const endpoint = button.dataset.endpoint;
  const text = button.dataset.audioText || '';
  const lang = button.dataset.lang || 'en-US';
  const rate = Number(button.dataset.rate || 1.0);

  if (!endpoint || !text) return;

  if (!('speechSynthesis' in window)) {
    alert('Your browser does not support listening playback.');
    return;
  }

  button.disabled = true;

  const label = button.querySelector('.play-label');
  const icon = button.querySelector('i');

  if (label) label.textContent = 'Loading English voice...';
  if (icon) icon.className = 'bi bi-hourglass-split';

  /*
   * Resolve the English voice BEFORE contacting the play-count endpoint.
   * If no English voice is available, no server-side play is consumed.
   */
  const voice = await resolveAssessmentEnglishVoice(lang);

  if (!voice) {
    if (label) label.textContent = 'English voice unavailable';
    if (icon) icon.className = 'bi bi-exclamation-triangle-fill';
    button.disabled = false;

    assessmentEnglishVoiceError();
    return;
  }

  if (label) label.textContent = 'Checking...';

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      }
    });

    if (!response.ok) {
      throw new Error(
        `Audio play endpoint returned HTTP ${response.status}`
      );
    }

    const data = await response.json();

    if (!data.allowed) {
      if (label) label.textContent = 'No plays left';
      if (icon) icon.className = 'bi bi-lock-fill';
      button.disabled = true;
      return;
    }

    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);

    // Use only the selected English voice.
    utterance.voice = voice;
    utterance.lang = voice.lang || lang;
    utterance.rate = rate;
    utterance.pitch = 1.0;

    if (label) label.textContent = 'Playing...';
    if (icon) icon.className = 'bi bi-volume-up-fill';

    console.info(
      `[speech] Assessment voice: ${voice.name} (${voice.lang})`
    );

    const finish = () => {
      if (data.remaining > 0) {
        if (label) {
          label.textContent = `Play again (${data.remaining} left)`;
        }
        if (icon) icon.className = 'bi bi-play-fill';
        button.disabled = false;
      } else {
        if (label) label.textContent = 'No plays left';
        if (icon) icon.className = 'bi bi-lock-fill';
        button.disabled = true;
      }
    };

    utterance.onend = finish;

    utterance.onerror = (event) => {
      console.error('[speech] Assessment TTS error:', event);
      finish();
    };

    window.speechSynthesis.speak(utterance);
  } catch (error) {
    console.error('[speech] Assessment audio error:', error);

    if (label) label.textContent = 'Play audio';
    if (icon) icon.className = 'bi bi-play-fill';
    button.disabled = false;
  }
}


(function initAssessmentTimer() {
  const timer = document.querySelector('.assessment-timer');
  const output = document.getElementById('assessmentTimer');

  if (!timer || !output) return;

  const startedAt = new Date(timer.dataset.startedAt);
  const durationMinutes = Number(
    timer.dataset.durationMinutes || 0
  );

  if (!durationMinutes) return;

  const endsAt =
    startedAt.getTime() +
    durationMinutes * 60 * 1000;

  function tick() {
    const remaining = Math.max(
      0,
      endsAt - Date.now()
    );

    const totalSeconds = Math.floor(
      remaining / 1000
    );

    const minutes = Math.floor(
      totalSeconds / 60
    );

    const seconds = totalSeconds % 60;

    output.textContent =
      `${String(minutes).padStart(2, '0')}:` +
      `${String(seconds).padStart(2, '0')}`;

    if (remaining <= 0) {
      timer.classList.add('expired');
      output.textContent = '00:00';
      return;
    }

    window.setTimeout(tick, 1000);
  }

  tick();
})();
