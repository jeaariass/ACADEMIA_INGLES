/*
 * English Practice Hub - TTS / Listening
 *
 * IMPORTANT:
 * Listening exercises must NEVER fall back to a Spanish voice.
 * The browser's Web Speech API uses voices installed/available on each device,
 * so we explicitly filter the voice list to English voices only.
 */

const listeningState = new Map();
let speechSessionToken = 0;

const ENGLISH_VOICE_WAIT_MS = 3000;

function normalizeVoiceLang(lang) {
  return String(lang || '')
    .trim()
    .replace(/_/g, '-')
    .toLowerCase();
}

function isEnglishVoice(voice) {
  if (!voice) return false;
  const lang = normalizeVoiceLang(voice.lang);
  return lang === 'en' || lang.startsWith('en-');
}

function getLoadedVoices() {
  if (!('speechSynthesis' in window)) return [];
  return window.speechSynthesis.getVoices() || [];
}

function scoreVoice(voice, requestedLang = 'en-US') {
  if (!isEnglishVoice(voice)) return Number.NEGATIVE_INFINITY;

  let score = 0;
  const name = String(voice.name || '').toLowerCase();
  const voiceLang = normalizeVoiceLang(voice.lang);
  const target = normalizeVoiceLang(requestedLang || 'en-US');

  // Prefer the requested English variant first.
  if (voiceLang === target) {
    score += 100;
  } else if (voiceLang.startsWith('en-')) {
    score += 60;
  } else if (voiceLang === 'en') {
    score += 50;
  }

  // Prefer commonly available high-quality English voices.
  const preferred = [
    'microsoft aria',
    'microsoft jenny',
    'microsoft guy',
    'microsoft ava',
    'microsoft andrew',
    'microsoft brian',
    'microsoft emma',
    'microsoft sonia',
    'microsoft ryan',
    'google us english',
    'google uk english female',
    'google uk english male',
    'samantha',
    'daniel',
    'serena',
    'ava'
  ];

  preferred.forEach((item, index) => {
    if (name.includes(item)) {
      score += Math.max(1, 40 - index);
    }
  });

  // "Natural" / online voices generally sound better when the browser exposes them.
  if (name.includes('natural')) score += 25;
  if (name.includes('online')) score += 12;

  if (voice.default) score += 2;

  return score;
}

function getEnglishVoices(requestedLang = 'en-US') {
  const voices = getLoadedVoices();

  return voices
    .filter(isEnglishVoice)
    .sort((a, b) => scoreVoice(b, requestedLang) - scoreVoice(a, requestedLang));
}

/*
 * Synchronous lookup.
 * This is useful after voices have already loaded.
 */
function getPreferredVoice(lang = 'en-US') {
  return getEnglishVoices(lang)[0] || null;
}

/*
 * Browsers may populate speechSynthesis voices asynchronously.
 * This waits briefly for the voiceschanged event instead of immediately
 * assuming that no English voice exists.
 */
function waitForSpeechVoices(timeoutMs = ENGLISH_VOICE_WAIT_MS) {
  return new Promise((resolve) => {
    if (!('speechSynthesis' in window)) {
      resolve([]);
      return;
    }

    const initial = getLoadedVoices();
    if (initial.length) {
      resolve(initial);
      return;
    }

    let settled = false;
    let timeoutId = null;

    const finish = () => {
      if (settled) return;
      settled = true;

      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }

      if (typeof window.speechSynthesis.removeEventListener === 'function') {
        window.speechSynthesis.removeEventListener('voiceschanged', handleVoicesChanged);
      }

      resolve(getLoadedVoices());
    };

    const handleVoicesChanged = () => {
      if (getLoadedVoices().length) {
        finish();
      }
    };

    if (typeof window.speechSynthesis.addEventListener === 'function') {
      window.speechSynthesis.addEventListener('voiceschanged', handleVoicesChanged);
    }

    // Trigger loading in browsers that lazy-load voices.
    window.speechSynthesis.getVoices();

    timeoutId = window.setTimeout(finish, timeoutMs);
  });
}

async function getPreferredVoiceAsync(lang = 'en-US') {
  let voice = getPreferredVoice(lang);
  if (voice) return voice;

  await waitForSpeechVoices();

  voice = getPreferredVoice(lang);
  return voice || null;
}

function englishVoiceUnavailableMessage() {
  return [
    'No English text-to-speech voice is available on this device.',
    '',
    'The listening exercise was NOT played with a Spanish voice.',
    '',
    'Please enable or install an English voice (English US or English UK)',
    'in Windows/macOS or try Chrome/Edge with an English voice available,',
    'then reload this page.'
  ].join('\n');
}

function notifyEnglishVoiceUnavailable() {
  alert(englishVoiceUnavailableMessage());
}

function makeUtterance(text, options = {}, voice = null) {
  if (!voice || !isEnglishVoice(voice)) {
    return null;
  }

  const utterance = new SpeechSynthesisUtterance(text);

  // Match the actual selected English voice. This avoids asking a British voice
  // to behave as Spanish/US/etc. while still preferring requestedLang in scoring.
  utterance.lang = voice.lang || options.lang || 'en-US';
  utterance.rate = Number(options.rate || 1.0);
  utterance.pitch = Number(options.pitch || 1.0);
  utterance.voice = voice;

  return utterance;
}

async function speakText(text, options = {}) {
  if (!('speechSynthesis' in window)) {
    alert('Your browser does not support text-to-speech.');
    return false;
  }

  if (!text) return false;

  const lang = options.lang || 'en-US';
  const voice = await getPreferredVoiceAsync(lang);

  if (!voice) {
    notifyEnglishVoiceUnavailable();
    return false;
  }

  const utterance = makeUtterance(text, options, voice);
  if (!utterance) {
    notifyEnglishVoiceUnavailable();
    return false;
  }

  speechSessionToken += 1;
  window.speechSynthesis.cancel();

  console.info(`[speech] English voice: ${voice.name} (${voice.lang})`);
  window.speechSynthesis.speak(utterance);

  return true;
}

function splitSpeechText(text, maxLength = 180) {
  const sentences = String(text)
    .replace(/\s+/g, ' ')
    .trim()
    .match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [];

  const chunks = [];
  let current = '';

  for (const sentence of sentences) {
    const clean = sentence.trim();
    if (!clean) continue;

    if ((current + ' ' + clean).trim().length <= maxLength) {
      current = (current + ' ' + clean).trim();
    } else {
      if (current) chunks.push(current);
      current = clean;
    }
  }

  if (current) chunks.push(current);
  return chunks;
}

async function speakLongText(text, options = {}) {
  if (!('speechSynthesis' in window)) {
    alert('Your browser does not support text-to-speech.');
    return false;
  }

  const chunks = splitSpeechText(
    text,
    Number(options.maxLength || 180)
  );

  if (!chunks.length) return false;

  const lang = options.lang || 'en-US';
  const voice = await getPreferredVoiceAsync(lang);

  if (!voice) {
    notifyEnglishVoiceUnavailable();
    return false;
  }

  speechSessionToken += 1;
  const token = speechSessionToken;
  window.speechSynthesis.cancel();

  console.info(`[speech] English voice: ${voice.name} (${voice.lang})`);

  let index = 0;

  function playNext() {
    if (token !== speechSessionToken || index >= chunks.length) {
      return;
    }

    const utterance = makeUtterance(
      chunks[index],
      {
        lang,
        rate: Number(options.rate || 1.03),
        pitch: Number(options.pitch || 1.0)
      },
      voice
    );

    if (!utterance) {
      notifyEnglishVoiceUnavailable();
      return;
    }

    utterance.onend = () => {
      index += 1;
      window.setTimeout(playNext, 40);
    };

    utterance.onerror = (event) => {
      console.error('[speech] TTS error:', event);
      index += 1;
      window.setTimeout(playNext, 40);
    };

    window.speechSynthesis.speak(utterance);
  }

  playNext();
  return true;
}

function updateListeningCounter(audioId, remaining) {
  const counter = document.querySelector(
    `[data-counter-for="${audioId}"]`
  );

  if (!counter) return;

  counter.textContent = remaining === 1
    ? '1 play remaining'
    : `${remaining} plays remaining`;
}

/*
 * Lesson listening.
 *
 * IMPORTANT:
 * We resolve a real English voice BEFORE consuming one of the local play counts.
 * If no English voice exists, playback is refused and no play is consumed.
 */
async function playListening(button) {
  const audioId = button.dataset.audioId || button.dataset.questionId;
  const maxPlays = Number(button.dataset.maxPlays || 2);
  const text = button.dataset.audioText || '';
  const lang = button.dataset.lang || 'en-US';
  const rate = Number(button.dataset.rate || 1.0);

  if (!listeningState.has(audioId)) {
    listeningState.set(audioId, maxPlays);
  }

  let remaining = listeningState.get(audioId);

  if (remaining <= 0) {
    button.disabled = true;
    updateListeningCounter(audioId, 0);
    return;
  }

  if (!('speechSynthesis' in window)) {
    alert('Your browser does not support listening playback.');
    return;
  }

  if (!text) return;

  const label = button.querySelector('.play-label');
  const icon = button.querySelector('i');

  button.disabled = true;
  if (label) label.textContent = 'Loading English voice...';
  if (icon) icon.className = 'bi bi-hourglass-split';

  const voice = await getPreferredVoiceAsync(lang);

  if (!voice) {
    if (label) label.textContent = 'English voice unavailable';
    if (icon) icon.className = 'bi bi-exclamation-triangle-fill';
    button.disabled = false;

    notifyEnglishVoiceUnavailable();
    return;
  }

  // Only consume a play after a valid English voice exists.
  remaining -= 1;
  listeningState.set(audioId, remaining);
  updateListeningCounter(audioId, remaining);

  speechSessionToken += 1;
  window.speechSynthesis.cancel();

  if (label) label.textContent = 'Playing...';
  if (icon) icon.className = 'bi bi-volume-up-fill';

  const utterance = makeUtterance(
    text,
    {lang, rate},
    voice
  );

  if (!utterance) {
    // Put the play back because nothing could be played.
    remaining += 1;
    listeningState.set(audioId, remaining);
    updateListeningCounter(audioId, remaining);

    if (label) label.textContent = 'Play audio';
    if (icon) icon.className = 'bi bi-play-fill';
    button.disabled = false;

    notifyEnglishVoiceUnavailable();
    return;
  }

  console.info(`[speech] Listening voice: ${voice.name} (${voice.lang})`);

  const finish = () => {
    if (label) {
      label.textContent = remaining > 0
        ? 'Play audio'
        : 'No plays left';
    }

    if (icon) {
      icon.className = remaining > 0
        ? 'bi bi-play-fill'
        : 'bi bi-lock-fill';
    }

    button.disabled = remaining <= 0;
  };

  utterance.onend = finish;

  utterance.onerror = (event) => {
    console.error('[speech] Listening TTS error:', event);
    finish();
  };

  window.speechSynthesis.speak(utterance);
}

/*
 * Debug helper.
 * Run this from the browser console if you need to inspect available voices:
 *
 *   debugEnglishVoices()
 */
function debugEnglishVoices() {
  const voices = getLoadedVoices();

  const rows = voices.map((voice) => ({
    name: voice.name,
    lang: voice.lang,
    english: isEnglishVoice(voice),
    default: voice.default,
    localService: voice.localService
  }));

  console.table(rows);
  return rows;
}

// Trigger voice loading as soon as the page is ready.
if ('speechSynthesis' in window) {
  window.speechSynthesis.getVoices();

  if (typeof window.speechSynthesis.addEventListener === 'function') {
    window.speechSynthesis.addEventListener('voiceschanged', () => {
      window.speechSynthesis.getVoices();
    });
  }
}
