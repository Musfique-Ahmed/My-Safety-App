/* Shared sticky header. Pages include:
 *   <link rel="stylesheet" href="/static/assets/css/header.css">
 *   <script src="/static/assets/js/api-base.js"></script>
 *   <script src="/static/assets/js/escape.js"></script>
 *   <script src="/static/assets/js/header.js"></script>
 *   ...
 *   <div id="app-header"></div>
 *
 * The header HTML is injected by renderHeader(); CSS classes follow the
 * Tailwind utility palette already in use across the app.
 */
(function () {
  function buildHeader() {
    var token = '';
    try { token = window.localStorage.getItem('auth_token') || ''; } catch (e) {}
    var userLabel = 'Hi, User!';
    try {
      var raw = window.localStorage.getItem('currentUser') || window.localStorage.getItem('mysafety_user');
      if (raw) {
        var u = JSON.parse(raw);
        userLabel = 'Hi, ' + (u.username || u.email || 'User') + '!';
      }
    } catch (e) {}

    var adminLink = token
      ? '<a href="/admin-dashboard" class="nav-link">Admin</a>'
      : '';

    return ''
      + '<header class="app-header">'
      + '  <div class="app-header__inner">'
      + '    <a href="/" class="app-header__brand">My Safety App</a>'
      + '    <nav class="app-header__nav">'
      + '      <a href="/dashboard" class="nav-link">Dashboard</a>'
      + '      <a href="/report-crime" class="nav-link">Report Crime</a>'
      + '      <a href="/missing-person" class="nav-link">Missing Persons</a>'
      + '      <a href="/wanted-criminals" class="nav-link">Wanted</a>'
      + '      <a href="/chatbox" class="nav-link">Chat</a>'
      +       adminLink
      + '    </nav>'
      + '    <div class="app-header__user">'
      +        window.escapeHtml(userLabel)
      + '      <button type="button" id="header-logout" class="header-btn">Logout</button>'
      + '    </div>'
      + '  </div>'
      + '</header>';
  }

  function attachLogout() {
    var btn = document.getElementById('header-logout');
    if (!btn) return;
    btn.addEventListener('click', function () {
      try {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('currentUser');
        localStorage.removeItem('currentUserId');
        localStorage.removeItem('mysafety_user');
      } catch (e) {}
      window.location.href = '/login';
    });
  }

  window.renderHeader = function () {
    var mount = document.getElementById('app-header');
    if (!mount) return;
    mount.outerHTML = buildHeader();
    attachLogout();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', window.renderHeader);
  } else {
    window.renderHeader();
  }
})();
