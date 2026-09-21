/*
 * English Practice Hub - TTS / Listening
 *
 * Audio is generated on the server (not with the browser's Web Speech API),
 * so playback sounds the same on every device and never depends on which
 * voices or language packs happen to be installed locally.
 */

const TTS_ENDPOINT = '/tts/speak';

const listeningState = new Map();
let speechSessionToken = 0;
let currentAudio = null;

function stopCurrentAudio() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.src = '';
    currentAudio = null;
  }
}

async function fetchSpeechAudio(text, { lang = 'en-US', rate = 1.0 } = {}) {
  const response = await fetch(TTS_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, lang, rate }),
  });

  if (!response.ok) {
    let message = 'The audio could not be generated. Please try again.';
    try {
      const data = await response.json();
      if (data && data.error) message = data.error;
    } catch (_err) {
      // response body was not JSON; keep the default message
    }
    throw new Error(message);
  }

  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

function notifySpeechError(message) {
  alert(message || 'The audio could not be played. Please try again.');
}

function playAudioUrl(url, token) {
  return new Promise((resolve) => {
    if (token !== speechSessionToken) {
      URL.revokeObjectURL(url);
      resolve();
      return;
    }

    stopCurrentAudio();
    const audio = new Audio(url);
    currentAudio = audio;

    const cleanup = () => {
      URL.revokeObjectURL(url);
      if (currentAudio === audio) currentAudio = null;
      resolve();
    };

    audio.onended = cleanup;
    audio.onerror = cleanup;
    audio.play().catch(cleanup);
  });
}

async function speakText(text, options = {}) {
  if (!text) return false;

  speechSessionToken += 1;
  const token = speechSessionToken;

  try {
    const url = await fetchSpeechAudio(text, options);
    await playAudioUrl(url, token);
    return true;
  } catch (err) {
    console.error('[speech] TTS error:', err);
    notifySpeechError(err.message);
    return false;
  }
}

async function speakLongText(text, options = {}) {
  // gTTS already tokenizes/paces long passages server-side, so no client-side
  // chunking is needed here.
  return speakText(text, options);
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
 * A local play count is only consumed once the audio has actually been
 * generated and is ready to play, so a failed request never burns a play.
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

  if (!text) return;

  const label = button.querySelector('.play-label');
  const icon = button.querySelector('i');

  button.disabled = true;
  if (label) label.textContent = 'Loading audio...';
  if (icon) icon.className = 'bi bi-hourglass-split';

  speechSessionToken += 1;
  const token = speechSessionToken;

  let url;
  try {
    url = await fetchSpeechAudio(text, { lang, rate });
  } catch (err) {
    console.error('[speech] Listening TTS error:', err);
    if (label) label.textContent = 'Audio unavailable';
    if (icon) icon.className = 'bi bi-exclamation-triangle-fill';
    button.disabled = false;
    notifySpeechError(err.message);
    return;
  }

  // Only consume a play now that audio is confirmed ready.
  remaining -= 1;
  listeningState.set(audioId, remaining);
  updateListeningCounter(audioId, remaining);

  if (label) label.textContent = 'Playing...';
  if (icon) icon.className = 'bi bi-volume-up-fill';

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

  await playAudioUrl(url, token);
  finish();
}

/*
 * Seekable audio player.
 *
 * A richer player for longer content (stories, reading/listening passages):
 * play/pause, a draggable seek bar, elapsed/remaining time - like scrubbing
 * through a song. Attach it by giving an element class="audio-player" with:
 *
 *   data-audio-text   text to synthesize
 *   data-lang         accent, e.g. "en-US"
 *   data-rate         playback rate used when generating the audio
 *   data-max-plays    times playback may be (re)started from the beginning
 *   data-unlimited    "true" to skip the play limit entirely
 *   data-endpoint     optional POST endpoint that must approve every new
 *                     play (formal assessments track this server-side so
 *                     reloading the page cannot reset it); the response is
 *                     expected as JSON {allowed, remaining}
 *
 * Pausing, resuming and dragging the seek bar are always free - only
 * starting a fresh playback consumes a play.
 */

const audioPlayerRoots = new Set();
const audioPlayerAudioGetters = new WeakMap();

function formatAudioTime(seconds) {
  if (!isFinite(seconds) || seconds < 0) seconds = 0;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

function pauseOtherAudioPlayers(except) {
  audioPlayerRoots.forEach((root) => {
    if (root === except) return;
    const getAudio = audioPlayerAudioGetters.get(root);
    const audioEl = getAudio && getAudio();
    if (audioEl && !audioEl.paused) audioEl.pause();
  });
}

function initAudioPlayer(root) {
  if (!root || root.dataset.playerReady) return;

  const text = root.dataset.audioText || '';
  const toggleBtn = root.querySelector('.audio-player-toggle');
  const seekInput = root.querySelector('.audio-player-seek');
  const elapsedEl = root.querySelector('.audio-player-elapsed');
  const remainingEl = root.querySelector('.audio-player-remaining');
  const playsEl = root.querySelector('.audio-player-plays');

  if (!text || !toggleBtn || !seekInput) return;
  root.dataset.playerReady = 'true';

  const lang = root.dataset.lang || 'en-US';
  const rate = Number(root.dataset.rate || 1.0);
  const unlimited = root.dataset.unlimited === 'true';
  const endpoint = root.dataset.endpoint || '';
  let remainingPlays = Number(root.dataset.maxPlays || 2);

  let audioEl = null;
  let seeking = false;
  let busy = false;

  audioPlayerRoots.add(root);
  audioPlayerAudioGetters.set(root, () => audioEl);

  function playsLabel(n) {
    return n === 1 ? '1 play remaining' : `${n} plays remaining`;
  }

  function updatePlaysLabel(label) {
    if (playsEl) playsEl.textContent = label;
  }

  if (!unlimited) updatePlaysLabel(playsLabel(Math.max(remainingPlays, 0)));

  function setIcon(playing) {
    toggleBtn.innerHTML = playing
      ? '<i class="bi bi-pause-fill"></i>'
      : '<i class="bi bi-play-fill"></i>';
  }

  function lockOut() {
    toggleBtn.disabled = true;
    updatePlaysLabel('No plays left');
  }

  async function approvePlay() {
    if (!endpoint) return true;
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      remainingPlays = Number(data.remaining || 0);
      if (!data.allowed) {
        lockOut();
        return false;
      }
      return true;
    } catch (err) {
      console.error('[audio-player] play-count check failed:', err);
      notifySpeechError('Could not verify remaining plays. Please try again.');
      return false;
    }
  }

  async function startNewPlayback() {
    if (!unlimited && !endpoint && remainingPlays <= 0) return;

    busy = true;
    toggleBtn.disabled = true;
    toggleBtn.innerHTML = '<i class="bi bi-hourglass-split"></i>';

    // Generate the audio BEFORE consuming a server-tracked play, so a failed
    // request never costs the student a play.
    let url;
    try {
      url = await fetchSpeechAudio(text, { lang, rate });
    } catch (err) {
      console.error('[audio-player] TTS error:', err);
      notifySpeechError(err.message);
      toggleBtn.disabled = false;
      setIcon(false);
      busy = false;
      return;
    }

    const approved = await approvePlay();
    if (!approved) {
      URL.revokeObjectURL(url);
      busy = false;
      toggleBtn.disabled = false;
      setIcon(false);
      return;
    }

    if (!unlimited && !endpoint) {
      remainingPlays -= 1;
    }
    if (!unlimited) updatePlaysLabel(playsLabel(Math.max(remainingPlays, 0)));

    pauseOtherAudioPlayers(root);

    audioEl = new Audio(url);

    audioEl.addEventListener('loadedmetadata', () => {
      seekInput.max = audioEl.duration || 0;
      seekInput.disabled = false;
    });
    audioEl.addEventListener('timeupdate', () => {
      if (seeking) return;
      seekInput.value = audioEl.currentTime;
      elapsedEl.textContent = formatAudioTime(audioEl.currentTime);
      remainingEl.textContent = `-${formatAudioTime((audioEl.duration || 0) - audioEl.currentTime)}`;
    });
    audioEl.addEventListener('play', () => setIcon(true));
    audioEl.addEventListener('pause', () => setIcon(false));
    audioEl.addEventListener('ended', () => {
      setIcon(false);
      URL.revokeObjectURL(url);
      if (!unlimited && remainingPlays <= 0) lockOut();
    });

    busy = false;
    toggleBtn.disabled = false;
    audioEl.play().catch(() => {});
  }

  toggleBtn.addEventListener('click', () => {
    if (busy) return;

    if (audioEl && !audioEl.ended) {
      if (audioEl.paused) {
        pauseOtherAudioPlayers(root);
        audioEl.play().catch(() => {});
      } else {
        audioEl.pause();
      }
      return;
    }

    startNewPlayback();
  });

  seekInput.addEventListener('input', () => {
    seeking = true;
    elapsedEl.textContent = formatAudioTime(Number(seekInput.value));
  });
  seekInput.addEventListener('change', () => {
    if (audioEl) audioEl.currentTime = Number(seekInput.value);
    seeking = false;
  });
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.audio-player').forEach(initAudioPlayer);
});
