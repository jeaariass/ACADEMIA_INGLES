/*
 * Formal assessment audio playback now uses the shared seekable
 * `.audio-player` component (see speech.js), which already supports a
 * `data-endpoint` attribute for server-verified play counts. No page-specific
 * audio code is needed here anymore.
 */

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
