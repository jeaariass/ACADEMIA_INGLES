function speakText(text){
  if (!('speechSynthesis' in window)){ alert('El navegador no soporta lectura por voz.'); return; }
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'en-US';
  utterance.rate = 0.9;
  speechSynthesis.speak(utterance);
}
