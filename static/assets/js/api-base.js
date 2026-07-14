/* Shared API base + Authorization header injection.
 *
 * Loaded by every page that calls the FastAPI backend. Pages should call
 * `resolveApiUrl(path)` for any fetch URL (returns absolute or root-relative
 * path) and the global `fetch` wrapper automatically attaches the bearer
 * token from localStorage.auth_token for non-GET requests to /api/admin/*
 * and /api/chat/*. Public reads (e.g. /api/crimes GET) stay un-authenticated.
 */
(function () {
  var base = '';
  if (typeof window !== 'undefined' && window.location && window.location.origin) {
    // Same-origin when served by FastAPI on :8000. Cross-origin in dev is handled
    // by the explicit API_BASE override at the top of admin_dashboard21.html.
    base = window.location.origin;
  }
  window.API_BASE = window.API_BASE || base;

  window.resolveApiUrl = function (path) {
    if (!path) return path;
    if (/^https?:\/\//i.test(path)) return path;
    if (path.charAt(0) !== '/') path = '/' + path;
    return window.API_BASE.replace(/\/$/, '') + path;
  };

  var _nativeFetch = window.fetch ? window.fetch.bind(window) : null;

  function _needsAuth(method, url) {
    var m = (method || 'GET').toUpperCase();
    if (m === 'GET' || m === 'HEAD') return false;
    return /\/api\/(admin|chat)\//.test(url);
  }

  window.fetch = function (input, init) {
    init = init || {};
    var url = typeof input === 'string' ? input : (input && input.url) || '';
    var method = (init.method || (input && input.method) || 'GET').toUpperCase();
    var headers = init.headers || (input && input.headers) || {};
    if (typeof Headers !== 'undefined' && headers instanceof Headers) {
      var obj = {};
      headers.forEach(function (v, k) { obj[k] = v; });
      headers = obj;
      init.headers = headers;
    }
    if (_needsAuth(method, url)) {
      var token = (window.localStorage && localStorage.getItem('auth_token')) || '';
      if (token && !headers['Authorization'] && !headers['authorization']) {
        headers['Authorization'] = 'Bearer ' + token;
        init.headers = headers;
      }
    }
    if (_nativeFetch) return _nativeFetch(input, init);
    return Promise.reject(new Error('fetch not available'));
  };
})();
