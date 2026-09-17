async function playAssessmentAudio(button) {
  const endpoint = button.dataset.endpoint;
  const text = button.dataset.audioText || '';
  const lang = button.dataset.lang || 'en-US';
  const rate = Number(button.dataset.rate || 1.0);

  if (!endpoint || !text) return;

  button.disabled = true;
  const label = button.querySelector('.play-label');
  const icon = button.querySelector('i');
  if (label) label.textContent = 'Checking...';

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {'X-Requested-With': 'XMLHttpRequest'}
    });
    const data = await response.json();

    if (!data.allowed) {
      if (label) label.textContent = 'No plays left';
      if (icon) icon.className = 'bi bi-lock-fill';
      button.disabled = true;
      return;
    }

    if (!('speechSynthesis' in window)) {
      alert('Your browser does not support listening playback.');
      button.disabled = false;
      return;
    }

    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang;
    utterance.rate = rate;

    if (typeof getPreferredVoice === 'function') {
      const voice = getPreferredVoice(lang);
      if (voice) utterance.voice = voice;
    }

    if (label) label.textContent = 'Playing...';
    if (icon) icon.className = 'bi bi-volume-up-fill';

    const finish = () => {
      if (data.remaining > 0) {
        if (label) label.textContent = `Play again (${data.remaining} left)`;
        if (icon) icon.className = 'bi bi-play-fill';
        button.disabled = false;
      } else {
        if (label) label.textContent = 'No plays left';
        if (icon) icon.className = 'bi bi-lock-fill';
        button.disabled = true;
      }
    };

    utterance.onend = finish;
    utterance.onerror = finish;
    speechSynthesis.speak(utterance);
  } catch (error) {
    console.error(error);
    if (label) label.textContent = 'Play audio';
    button.disabled = false;
  }
}

(function initAssessmentTimer() {
  const timer = document.querySelector('.assessment-timer');
  const output = document.getElementById('assessmentTimer');
  if (!timer || !output) return;

  const startedAt = new Date(timer.dataset.startedAt);
  const durationMinutes = Number(timer.dataset.durationMinutes || 0);
  if (!durationMinutes) return;

  const endsAt = startedAt.getTime() + durationMinutes * 60 * 1000;

  function tick() {
    const remaining = Math.max(0, endsAt - Date.now());
    const totalSeconds = Math.floor(remaining / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    output.textContent = `${String(minutes).padStart(2,'0')}:${String(seconds).padStart(2,'0')}`;

    if (remaining <= 0) {
      timer.classList.add('expired');
      output.textContent = '00:00';
      return;
    }
    setTimeout(tick, 1000);
  }

  tick();
})();
