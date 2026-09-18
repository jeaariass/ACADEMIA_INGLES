(() => {
  const root = document.querySelector('.speaking-practice-card');
  if (!root) return;
  const start = document.getElementById('startSpeaking');
  const stop = document.getElementById('stopSpeaking');
  const save = document.getElementById('saveSpeaking');
  const transcriptEl = document.getElementById('speechTranscript');
  const status = document.getElementById('speechStatus');
  const feedback = document.getElementById('speakingFeedback');
  const orb = document.getElementById('micOrb');
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  let startedAt = null;
  let endedAt = null;
  let confidence = null;

  function enableSave() { save.disabled = !transcriptEl.value.trim(); }
  transcriptEl.addEventListener('input', enableSave);

  if (!Recognition) {
    status.textContent = 'Live speech recognition is not available in this browser. You can still type your transcript and save the practice.';
    start.disabled = true;
    transcriptEl.placeholder = 'Type what you said here.';
  } else {
    recognition = new Recognition();
    recognition.lang = 'en-US';
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    let finalText = '';

    recognition.onstart = () => { startedAt = performance.now(); endedAt = null; finalText = ''; confidence = null; transcriptEl.value = ''; status.textContent = 'Listening… speak naturally.'; orb.classList.add('is-listening'); start.disabled = true; stop.disabled = false; };
    recognition.onresult = (event) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const text = result[0].transcript;
        if (result.isFinal) { finalText += text + ' '; if (Number.isFinite(result[0].confidence)) confidence = result[0].confidence; }
        else interim += text;
      }
      transcriptEl.value = (finalText + interim).trim(); enableSave();
    };
    recognition.onerror = (event) => { status.textContent = `Microphone/recognition error: ${event.error}. You may type the transcript manually.`; };
    recognition.onend = () => { endedAt = performance.now(); orb.classList.remove('is-listening'); start.disabled = false; stop.disabled = true; status.textContent = transcriptEl.value.trim() ? 'Recognition stopped. Review the transcript, then save.' : 'No speech was captured. Try again.'; enableSave(); };
    start.addEventListener('click', () => { try { recognition.start(); } catch (_) {} });
    stop.addEventListener('click', () => { try { recognition.stop(); } catch (_) {} });
  }

  save.addEventListener('click', async () => {
    const transcript = transcriptEl.value.trim(); if (!transcript) return;
    save.disabled = true; save.textContent = 'Saving…';
    const duration = startedAt ? ((endedAt || performance.now()) - startedAt) / 1000 : null;
    try {
      const response = await fetch(root.dataset.endpoint, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({transcript, confidence, duration_seconds:duration})});
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || 'Could not save speaking practice.');
      const m = data.metrics;
      const cards = [
        ['Words', m.word_count],
        ['Speaking pace', m.wpm == null ? '—' : `${m.wpm} wpm`],
        ['Target vocabulary', `${m.target_hits}/${m.target_total}`],
        ['Recognition confidence', m.confidence_pct == null ? '—' : `${m.confidence_pct}%`]
      ];
      if (m.similarity != null) cards.splice(1,0,['Transcript similarity', `${m.similarity}%`]);
      if (m.coverage != null) cards.splice(2,0,['Expected-word coverage', `${m.coverage}%`]);
      feedback.innerHTML = `<div class="speaking-feedback-grid">${cards.map(([a,b])=>`<div><span>${a}</span><strong>${b}</strong></div>`).join('')}</div><p><i class="bi bi-info-circle"></i> ${data.note}</p>`;
      feedback.classList.remove('d-none');
    } catch (err) { alert(err.message); }
    finally { save.disabled = false; save.innerHTML = 'Save practice <i class="bi bi-check-lg"></i>'; }
  });
})();
