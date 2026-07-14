/* Shared HTML escape helper. Replaces the per-page copies that existed in
 * admin_dashboard21.html and missing_person.html. Use before any
 * .innerHTML interpolation of untrusted data.
 */
(function () {
  if (typeof window.escapeHtml === 'function') return; // already defined
  var ESCAPE_MAP = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
    '/': '&#x2F;',
  };
  window.escapeHtml = function (input) {
    if (input === null || input === undefined) return '';
    return String(input).replace(/[&<>"'/]/g, function (c) {
      return ESCAPE_MAP[c];
    });
  };
})();
