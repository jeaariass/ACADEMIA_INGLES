(() => {
  const body = document.getElementById('libraryReadingBody');
  const toolbar = document.getElementById('selectionToolbar');
  const modalElement = document.getElementById('saveVocabularyModal');
  const selectedTextBox = document.getElementById('selectedVocabularyText');
  const translationInput = document.getElementById('selectedVocabularyTranslation');
  const notesInput = document.getElementById('selectedVocabularyNotes');
  const errorBox = document.getElementById('saveVocabularyError');
  const saveButton = document.getElementById('confirmSaveVocabulary');
  const translatorButton = document.getElementById('openTranslatorFromModal');
  const config = window.LIBRARY_CONFIG || {};

  if (!body || !toolbar || !modalElement || !config.saveEndpoint) return;

  const modal = window.bootstrap ? new bootstrap.Modal(modalElement) : null;
  let selectedText = '';
  let selectedContext = '';

  function normalizeSelection(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function selectionIsInsideReading(selection) {
    if (!selection || selection.rangeCount === 0) return false;
    const range = selection.getRangeAt(0);
    const node = range.commonAncestorContainer.nodeType === Node.TEXT_NODE
      ? range.commonAncestorContainer.parentElement
      : range.commonAncestorContainer;
    return node && body.contains(node);
  }

  function getSelectionContext(selection) {
    if (!selection || selection.rangeCount === 0) return '';
    const range = selection.getRangeAt(0);
    let node = range.commonAncestorContainer.nodeType === Node.TEXT_NODE
      ? range.commonAncestorContainer.parentElement
      : range.commonAncestorContainer;
    const paragraph = node && node.closest ? node.closest('p') : null;
    const text = normalizeSelection(paragraph ? paragraph.textContent : body.textContent);
    if (text.length <= 260) return text;
    const target = normalizeSelection(selection.toString());
    const index = text.toLowerCase().indexOf(target.toLowerCase());
    if (index < 0) return text.slice(0, 257) + '...';
    const start = Math.max(0, index - 100);
    const end = Math.min(text.length, index + target.length + 120);
    return (start > 0 ? '...' : '') + text.slice(start, end) + (end < text.length ? '...' : '');
  }

  function hideToolbar() {
    toolbar.hidden = true;
  }

  function showToolbarForSelection() {
    const selection = window.getSelection();
    if (!selectionIsInsideReading(selection)) {
      hideToolbar();
      return;
    }

    const text = normalizeSelection(selection.toString());
    if (!text || text.length > 220) {
      hideToolbar();
      return;
    }

    selectedText = text;
    selectedContext = getSelectionContext(selection);

    const rect = selection.getRangeAt(0).getBoundingClientRect();
    toolbar.hidden = false;

    const toolbarWidth = toolbar.offsetWidth || 270;
    const left = Math.min(
      window.innerWidth - toolbarWidth - 12,
      Math.max(12, rect.left + (rect.width / 2) - (toolbarWidth / 2))
    );
    const top = Math.max(12, rect.top + window.scrollY - toolbar.offsetHeight - 10);

    toolbar.style.left = `${left}px`;
    toolbar.style.top = `${top}px`;
  }

  function openTranslator(text) {
    const url = 'https://translate.google.com/?sl=en&tl=es&op=translate&text=' + encodeURIComponent(text);
    window.open(url, '_blank', 'noopener,noreferrer');
  }

  body.addEventListener('mouseup', () => window.setTimeout(showToolbarForSelection, 0));
  body.addEventListener('keyup', () => window.setTimeout(showToolbarForSelection, 0));
  window.addEventListener('scroll', hideToolbar, { passive: true });

  document.addEventListener('mousedown', (event) => {
    if (!toolbar.contains(event.target) && !body.contains(event.target)) hideToolbar();
  });

  toolbar.addEventListener('click', (event) => {
    const button = event.target.closest('[data-selection-action]');
    if (!button || !selectedText) return;
    const action = button.dataset.selectionAction;

    if (action === 'listen') {
      if (typeof speakLongText === 'function') {
        speakLongText(selectedText, { lang: 'en-US', rate: 0.92 });
      }
    } else if (action === 'translate') {
      openTranslator(selectedText);
    } else if (action === 'save') {
      selectedTextBox.textContent = selectedText;
      translationInput.value = '';
      notesInput.value = '';
      errorBox.classList.add('d-none');
      hideToolbar();
      if (modal) modal.show();
    }
  });

  translatorButton.addEventListener('click', () => {
    if (selectedText) openTranslator(selectedText);
  });

  saveButton.addEventListener('click', async () => {
    if (!selectedText) return;
    saveButton.disabled = true;
    errorBox.classList.add('d-none');

    try {
      const response = await fetch(config.saveEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({
          text: selectedText,
          translation: translationInput.value.trim(),
          notes: notesInput.value.trim(),
          context: selectedContext,
          article_id: config.articleId
        })
      });

      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error || 'Could not save this vocabulary item.');
      }

      if (modal) modal.hide();
      const message = data.created ? 'Saved to My Vocabulary.' : 'Vocabulary entry updated.';
      const toast = document.createElement('div');
      toast.className = 'library-save-toast';
      toast.innerHTML = `<i class="bi bi-check-circle-fill"></i><span>${message}</span>`;
      document.body.appendChild(toast);
      window.setTimeout(() => toast.classList.add('show'), 10);
      window.setTimeout(() => {
        toast.classList.remove('show');
        window.setTimeout(() => toast.remove(), 250);
      }, 2200);
    } catch (error) {
      errorBox.textContent = error.message;
      errorBox.classList.remove('d-none');
    } finally {
      saveButton.disabled = false;
    }
  });
})();
