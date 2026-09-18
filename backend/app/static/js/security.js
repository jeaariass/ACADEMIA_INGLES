(function initAppSecurity() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  const token = meta ? meta.content : '';
  if (!token) return;

  function secureForm(form) {
    if (!form || form.tagName !== 'FORM') return;
    const method = String(form.getAttribute('method') || 'get').toLowerCase();
    if (method === 'get') return;
    if (form.querySelector('input[name="_csrf_token"]')) return;
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = '_csrf_token';
    input.value = token;
    form.appendChild(input);
  }

  document.querySelectorAll('form').forEach(secureForm);
  document.addEventListener('submit', (event) => secureForm(event.target), true);

  const originalFetch = window.fetch.bind(window);
  window.fetch = function secureFetch(input, init) {
    const options = Object.assign({}, init || {});
    const method = String(options.method || (input && input.method) || 'GET').toUpperCase();
    const unsafe = !['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method);

    let url;
    try {
      url = new URL(typeof input === 'string' ? input : input.url, window.location.href);
    } catch (_) {
      return originalFetch(input, options);
    }

    if (unsafe && url.origin === window.location.origin) {
      const headers = new Headers((input && input.headers) || {});
      new Headers(options.headers || {}).forEach((value, key) => headers.set(key, value));
      if (!headers.has('X-CSRF-Token')) headers.set('X-CSRF-Token', token);
      options.headers = headers;
    }
    return originalFetch(input, options);
  };
})();
