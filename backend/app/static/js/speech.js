const listeningState = new Map();
let speechSessionToken = 0;

function scoreVoice(voice, lang) {
  let score = 0;
  const name = (voice.name || '').toLowerCase();
  const voiceLang = (voice.lang || '').toLowerCase();
  const target = lang.toLowerCase();

  if (voiceLang === target) score += 50;
  else if (voiceLang.startsWith(target.split('-')[0])) score += 30;

  const preferred = [
    'google us english', 'google uk english',
    'microsoft aria', 'microsoft jenny', 'microsoft guy',
    'samantha', 'ava', 'daniel', 'serena'
  ];
  preferred.forEach((item, index) => {
    if (name.includes(item)) score += 25 - index;
  });

  if (voice.default) score += 3;
  return score;
}

function getPreferredVoice(lang = 'en-US') {
  if (!('speechSynthesis' in window)) return null;
  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) return null;

  return [...voices].sort(
    (a, b) => scoreVoice(b, lang) - scoreVoice(a, lang)
  )[0] || null;
}

function makeUtterance(text, options = {}) {
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = options.lang || 'en-US';
  utterance.rate = Number(options.rate || 1.0);
  utterance.pitch = Number(options.pitch || 1.0);

  const voice = getPreferredVoice(utterance.lang);
  if (voice) utterance.voice = voice;
  return utterance;
}

function speakText(text, options = {}) {
  if (!('speechSynthesis' in window)) {
    alert('Your browser does not support text-to-speech.');
    return false;
  }
  if (!text) return false;

  speechSessionToken += 1;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(makeUtterance(text, options));
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

function speakLongText(text, options = {}) {
  if (!('speechSynthesis' in window)) {
    alert('Your browser does not support text-to-speech.');
    return false;
  }

  const chunks = splitSpeechText(text, Number(options.maxLength || 180));
  if (!chunks.length) return false;

  speechSessionToken += 1;
  const token = speechSessionToken;
  window.speechSynthesis.cancel();

  let index = 0;

  function playNext() {
    if (token !== speechSessionToken || index >= chunks.length) return;

    const utterance = makeUtterance(chunks[index], {
      lang: options.lang || 'en-US',
      rate: Number(options.rate || 1.03),
      pitch: Number(options.pitch || 1.0)
    });

    utterance.onend = () => {
      index += 1;
      window.setTimeout(playNext, 40);
    };

    utterance.onerror = () => {
      index += 1;
      window.setTimeout(playNext, 40);
    };

    window.speechSynthesis.speak(utterance);
  }

  playNext();
  return true;
}

function updateListeningCounter(audioId, remaining) {
  const counter = document.querySelector(`[data-counter-for="${audioId}"]`);
  if (!counter) return;
  counter.textContent = remaining === 1
    ? '1 play remaining'
    : `${remaining} plays remaining`;
}

function playListening(button) {
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

  remaining -= 1;
  listeningState.set(audioId, remaining);
  updateListeningCounter(audioId, remaining);

  speechSessionToken += 1;
  window.speechSynthesis.cancel();

  const label = button.querySelector('.play-label');
  const icon = button.querySelector('i');
  button.disabled = true;

  if (label) label.textContent = 'Playing...';
  if (icon) icon.className = 'bi bi-volume-up-fill';

  const utterance = makeUtterance(text, { lang, rate });

  const finish = () => {
    if (label) label.textContent = remaining > 0 ? 'Play audio' : 'No plays left';
    if (icon) {
      icon.className = remaining > 0 ? 'bi bi-play-fill' : 'bi bi-lock-fill';
    }
    button.disabled = remaining <= 0;
  };

  utterance.onend = finish;
  utterance.onerror = finish;
  window.speechSynthesis.speak(utterance);
}

if ('speechSynthesis' in window) {
  window.speechSynthesis.getVoices();
  window.speechSynthesis.onvoiceschanged = () => {
    window.speechSynthesis.getVoices();
  };
}
