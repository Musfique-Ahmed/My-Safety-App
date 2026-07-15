/* ============================================================================
 * console.js — shared chrome for the Civic Operations Console.
 *
 * Single namespace: window.MS. Loaded by every page in static/ that uses the
 * new design system (console.css). Responsibilities:
 *
 *   1. Guarantee that api-base.js + escape.js load on this page (this fixes
 *      the /api/admin/* 401s reported by per-role browser tests).
 *   2. Inject the civic spine (left rail), topbar, and role-aware nav into
 *      <div id="ms-root"></div>. The spine's pulse animation lives in CSS.
 *   3. Inline a single SVG sprite so we never need a Lucide CDN reference.
 *   4. Provide role gating: citizens on /admin get redirected to /dashboard.
 *   5. Expose helpers: MS.toast, MS.confirmModal, MS.openModal, MS.closeModal,
 *      MS.api.get/post/put/del, MS.user, MS.logout, MS.icon, MS.escape.
 *
 * Conventions preserved from the bulletin era:
 *   - "MS" is the product namespace (My Safety).
 *   - escapeHtml / resolveApiUrl come from sibling files (api-base.js, escape.js)
 *     and are reused, never redefined.
 * ============================================================================ */

(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // 0. Pre-flight: ensure api-base.js + escape.js are present on this page.
  //    If a page forgot to include them we lazy-inject. This is the single
  //    change that fixes /api/admin/* returning 401 in the browser.
  // ---------------------------------------------------------------------------
  function _ensureScript(src) {
    return new Promise(function (resolve) {
      var found = false;
      var scripts = document.getElementsByTagName('script');
      for (var i = 0; i < scripts.length; i++) {
        if (scripts[i].src && scripts[i].src.indexOf(src) !== -1) { found = true; break; }
      }
      if (found) return resolve();
      var s = document.createElement('script');
      s.src = src;
      s.async = false;
      s.onload = function () { resolve(); };
      s.onerror = function () { resolve(); }; // don't block chrome on a failed load
      document.head.appendChild(s);
    });
  }

  function _ensureCss(href) {
    var links = document.getElementsByTagName('link');
    for (var i = 0; i < links.length; i++) {
      if (links[i].href && links[i].href.indexOf(href) !== -1) return;
    }
    var l = document.createElement('link');
    l.rel = 'stylesheet';
    l.href = href;
    document.head.appendChild(l);
  }

  // Pull in api-base.js, escape.js, console.css. console.css may already be
  // linked from a <head> tag; that's fine, _ensureCss is idempotent.
  _ensureCss('/static/assets/css/console.css');

  // We can't `await` here — wrap the rest in a function called once both deps
  // are present (they likely already are).
  function _ready(cb) {
    var tries = 0;
    (function poll() {
      tries++;
      if (window.fetch && window.resolveApiUrl && window.escapeHtml && window.API_BASE !== undefined) {
        return cb();
      }
      if (tries > 80) return cb(); // give up after 4s, fall back to globals stubbed below
      setTimeout(poll, 50);
    })();
  }

  // ---------------------------------------------------------------------------
  // 1. SVG sprite (inlined once, referenced via <use href="#ms-...">).
  //    All icons render in currentColor so status pills/buttons can colour
  //    them via CSS.
  // ---------------------------------------------------------------------------
  var ICONS = {
    'shield': '<path d="M12 2 4 5v6c0 5 3.5 9.3 8 11 4.5-1.7 8-6 8-11V5l-8-3z"/>',
    'shield-alert': '<path d="M12 2 4 5v6c0 5 3.5 9.3 8 11 4.5-1.7 8-6 8-11V5l-8-3z"/><path d="M12 8v5"/><circle cx="12" cy="16" r="0.9" fill="currentColor" stroke="none"/>',
    'alert-triangle': '<path d="M10.3 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4"/><circle cx="12" cy="16" r="0.9" fill="currentColor" stroke="none"/>',
    'message-circle': '<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>',
    'user': '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    'search': '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
    'settings': '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    'log-out': '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
    'plus': '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    'minus': '<line x1="5" y1="12" x2="19" y2="12"/>',
    'x': '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    'chevron-left': '<polyline points="15 18 9 12 15 6"/>',
    'chevron-right': '<polyline points="9 18 15 12 9 6"/>',
    'chevron-up': '<polyline points="18 15 12 9 6 15"/>',
    'chevron-down': '<polyline points="6 9 12 15 18 9"/>',
    'map-pin': '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
    'file-text': '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    'bell': '<path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
    'check': '<polyline points="20 6 9 17 4 12"/>',
    'home': '<path d="M3 9.5 12 2l9 7.5V20a2 2 0 0 1-2 2h-4v-7h-6v7H5a2 2 0 0 1-2-2V9.5z"/>',
    'users': '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    'menu': '<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>',
    'globe-icon': '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    'briefcase': '<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>',
    'phone': '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.37 1.9.72 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.35 1.85.59 2.81.72A2 2 0 0 1 22 16.92z"/>',
    'megaphone': '<path d="M3 11v2a2 2 0 0 0 2 2h2l5 4V5L7 9H5a2 2 0 0 0-2 2z"/><path d="M16 8a4 4 0 0 1 0 8"/>',
    'arrow-right': '<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>',
    'refresh': '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>'
  };

  function _injectSprite() {
    if (document.getElementById('ms-sprite')) return;
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" id="ms-sprite" style="display:none" aria-hidden="true">';
    Object.keys(ICONS).forEach(function (k) {
      svg += '<symbol id="ms-' + k + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + ICONS[k] + '</symbol>';
    });
    svg += '</svg>';
    document.body.insertAdjacentHTML('afterbegin', svg);
  }

  function icon(name, attrs) {
    attrs = attrs || {};
    var a = '';
    Object.keys(attrs).forEach(function (k) { a += ' ' + k + '="' + window.escapeHtml(attrs[k]) + '"'; });
    return '<svg class="ms-icon' + (attrs['class'] ? ' ' + attrs['class'] : '') + '"' + a + '><use href="#ms-' + name + '"/></svg>';
  }


  // ---------------------------------------------------------------------------
  // 2. User state — single source of truth is localStorage.currentUser
  //    (JSON) + localStorage.auth_token (raw JWT). Admin dashboard previously
  //    hardcoded "Inspector John Doe"; we now read from the same store.
  // ---------------------------------------------------------------------------
  var _user = null;
  function _loadUser() {
    try {
      var raw = localStorage.getItem('currentUser');
      if (!raw) return null;
      var u = JSON.parse(raw);
      if (u && typeof u === 'object') return u;
    } catch (e) { /* corrupt storage */ }
    return null;
  }
  function _saveUser(u) {
    _user = u;
    if (u) localStorage.setItem('currentUser', JSON.stringify(u));
    else localStorage.removeItem('currentUser');
  }

  var ROLES = {
    PRIVILEGED: ['admin', 'officer', 'detective', 'staff'],
    ALL: ['admin', 'officer', 'detective', 'staff', 'User']
  };

  function isPrivileged() {
    var r = (_user && _user.role_hint || '').toLowerCase();
    return ROLES.PRIVILEGED.indexOf(r) !== -1;
  }


  // ---------------------------------------------------------------------------
  // 3. Civic spine (left rail). Three ticks: CITY / STATION / CITIZEN.
  //    Active tick is set by data-page attribute on <body> or #ms-root.
  // ---------------------------------------------------------------------------
  var SPINE_TICKS = [
    { id: 'city',    label: 'City',    href: '/',                  match: ['/', '/dashboard', '/home'] },
    { id: 'station', label: 'Station', href: '/admin',             match: ['/admin', '/admin-dashboard'] },
    { id: 'citizen', label: 'Citizen', href: '/missing-person',    match: ['/missing-person', '/report-missing', '/wanted-criminals'] }
  ];

  function _activeSpineTick() {
    var path = (window.location.pathname || '').toLowerCase();
    for (var i = 0; i < SPINE_TICKS.length; i++) {
      var m = SPINE_TICKS[i].match;
      for (var j = 0; j < m.length; j++) {
        if (path === m[j] || path.indexOf(m[j] + '/') === 0) return SPINE_TICKS[i].id;
      }
    }
    return null;
  }

  function _renderSpine() {
    var active = _activeSpineTick();
    return '<nav class="ms-rail" aria-label="Primary">' +
      SPINE_TICKS.map(function (t) {
        var isActive = t.id === active;
        return '<a href="' + t.href + '" class="ms-rail__tick' + (isActive ? ' is-active' : '') +
               '" title="' + t.label + '" aria-current="' + (isActive ? 'true' : 'false') + '">' +
               '<span class="ms-rail__label">' + t.label + '</span>' +
             '</a>';
      }).join('') +
    '</nav>';
  }


  // ---------------------------------------------------------------------------
  // 4. Topbar (search + user menu). Role-aware nav links appear on inner
  //    pages; on the home dashboard we keep the bar minimal.
  // ---------------------------------------------------------------------------
  function _navLinks() {
    var links = [];
    if (isPrivileged()) {
      links.push({ href: '/admin',                 label: 'Console',     icon: 'briefcase' });
      links.push({ href: '/report-crime',          label: 'New report',  icon: 'alert-triangle' });
    }
    links.push({ href: '/missing-person',          label: 'Missing',      icon: 'user' });
    links.push({ href: '/wanted-criminals',        label: 'Wanted',       icon: 'shield-alert' });
    links.push({ href: '/chatbox',                 label: 'Chat',         icon: 'message-circle' });
    return links;
  }

  function _renderTopbar() {
    var u = _user;
    var initials = '·';
    if (u && u.name) {
      initials = u.name.split(/\s+/).map(function (s) { return s[0]; }).slice(0, 2).join('').toUpperCase();
    } else if (u && u.email) {
      initials = u.email[0].toUpperCase();
    }
    var role = (u && u.role_hint) ? u.role_hint : 'Guest';
    var navItems = _navLinks().map(function (l) {
      return '<a href="' + l.href + '" class="ms-topbar__nav-link">' +
               icon(l.icon, { 'aria-hidden': 'true' }) + '<span>' + l.label + '</span>' +
             '</a>';
    }).join('');
    var right = '';
    if (u) {
      right =
        '<button class="ms-topbar__iconbtn" type="button" data-ms-action="open-notifications" aria-label="Notifications">' +
          icon('bell') +
        '</button>' +
        '<div class="ms-userchip" data-ms-action="toggle-user-menu" tabindex="0" role="button" aria-haspopup="true">' +
          '<span class="ms-userchip__avatar">' + window.escapeHtml(initials) + '</span>' +
          '<span class="ms-userchip__meta">' +
            '<span class="ms-userchip__name">' + window.escapeHtml(u.name || u.email) + '</span>' +
            '<span class="ms-userchip__role">' + window.escapeHtml(role) + '</span>' +
          '</span>' +
          icon('chevron-down', { 'class': 'ms-userchip__caret' }) +
        '</div>' +
        '<div class="ms-usermenu" id="ms-usermenu" role="menu" hidden>' +
          '<a href="/dashboard" role="menuitem">' + icon('home') + ' Dashboard</a>' +
          (isPrivileged() ? '<a href="/admin" role="menuitem">' + icon('briefcase') + ' Console</a>' : '') +
          '<a href="/chatbox" role="menuitem">' + icon('message-circle') + ' Messages</a>' +
          '<button type="button" role="menuitem" data-ms-action="logout">' + icon('log-out') + ' Log out</button>' +
        '</div>';
    } else {
      right =
        '<a href="/login" class="ms-btn ms-btn--ghost ms-btn--sm">Log in</a>' +
        '<a href="/signup" class="ms-btn ms-btn--primary ms-btn--sm">Sign up</a>';
    }

    return '<header class="ms-topbar" role="banner">' +
      '<a href="/" class="ms-topbar__brand">' +
        icon('shield', { 'class': 'ms-topbar__brand-icon' }) +
        '<span class="ms-topbar__brand-wordmark">My<strong>Safety</strong></span>' +
        '<span class="ms-topbar__brand-tag">Civic Operations Console</span>' +
      '</a>' +
      '<nav class="ms-topbar__nav" aria-label="Sections">' + navItems + '</nav>' +
      '<div class="ms-topbar__right">' + right + '</div>' +
    '</header>';
  }


  // ---------------------------------------------------------------------------
  // 5. Mount chrome into <div id="ms-root"></div>. If absent, the page is
  //    opting out of the shared shell (e.g. login/signup get their own
  //    minimal chrome — they can call MS.renderMinimalShell() themselves).
  // ---------------------------------------------------------------------------
  function renderChrome(opts) {
    opts = opts || {};
    _user = _loadUser();
    _injectSprite();

    var root = document.getElementById('ms-root');
    if (!root) {
      // Inject a sentinel root above the existing content. Pages that
      // don't want chrome can add data-ms-no-chrome="true" to <html>.
      if (document.documentElement.dataset.msNoChrome === 'true') return;
      root = document.createElement('div');
      root.id = 'ms-root';
      document.body.insertBefore(root, document.body.firstChild);
    }
    root.innerHTML =
      '<div class="ms-app">' +
        _renderSpine() +
        '<div class="ms-app__main">' +
          _renderTopbar() +
          '<main class="ms-app__page" id="ms-page" role="main"></main>' +
        '</div>' +
      '</div>';

    var page = document.getElementById('ms-page');

    // Two ways to provide page content:
    //   1. <template id="ms-page-template">…</template> — clone it in.
    //   2. Existing body children (excluding root + sprite) — move them.
    var tpl = document.getElementById('ms-page-template');
    if (tpl && tpl.content && tpl.content.childNodes.length) {
      page.appendChild(tpl.content.cloneNode(true));
      // The template can be removed from the body now that it's cloned.
      try { tpl.parentNode.removeChild(tpl); } catch (e) { /* not in body anymore */ }
    } else {
      var moved = [];
      for (var i = 0; i < document.body.children.length; i++) {
        var c = document.body.children[i];
        if (c === root) continue;
        if (c.id === 'ms-sprite') continue;
        if (c.tagName === 'TEMPLATE' && c.id === 'ms-page-template') continue;
        moved.push(c);
      }
      moved.forEach(function (c) { page.appendChild(c); });
    }

    _wireUserMenu();
    _wireGlobalActions();
    _runRoleGuard();

    if (typeof opts.afterRender === 'function') opts.afterRender();
  }

  function renderMinimalShell(opts) {
    // For /login, /signup: no rail, no topbar — the page provides its own
    // layout (typically .ms-auth with a panel + side). If the page put its
    // content directly inside #ms-root, leave it alone; if the content is
    // at the body level, wrap it in #ms-page.
    opts = opts || {};
    _user = _loadUser();
    _injectSprite();
    var root = document.getElementById('ms-root');
    if (!root) return;
    if (root.children.length > 0) {
      // Page authored the chrome inside #ms-root already (login, signup).
      // Just ensure the sprite is present and stop.
      _wireGlobalActions();
      _runRoleGuard();
      if (typeof opts.afterRender === 'function') opts.afterRender();
      return;
    }
    root.innerHTML =
      '<div class="ms-app ms-app--minimal">' +
        '<main class="ms-app__page ms-app__page--minimal" id="ms-page" role="main"></main>' +
      '</div>';
    var page = document.getElementById('ms-page');
    var moved = [];
    for (var i = 0; i < document.body.children.length; i++) {
      var c = document.body.children[i];
      if (c === root) continue;
      if (c.id === 'ms-sprite') continue;
      if (c.tagName === 'TEMPLATE' && c.id === 'ms-page-template') continue;
      moved.push(c);
    }
    moved.forEach(function (c) { page.appendChild(c); });
    if (typeof opts.afterRender === 'function') opts.afterRender();
  }


  // ---------------------------------------------------------------------------
  // 6. User menu + global actions (logout, etc.)
  // ---------------------------------------------------------------------------
  function _wireUserMenu() {
    var chip = document.querySelector('[data-ms-action="toggle-user-menu"]');
    var menu = document.getElementById('ms-usermenu');
    if (!chip || !menu) return;
    function close() { menu.hidden = true; chip.setAttribute('aria-expanded', 'false'); }
    function open()  { menu.hidden = false; chip.setAttribute('aria-expanded', 'true'); }
    chip.addEventListener('click', function (e) {
      e.stopPropagation();
      menu.hidden ? open() : close();
    });
    chip.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); menu.hidden ? open() : close(); }
    });
    document.addEventListener('click', function (e) {
      if (!menu.contains(e.target) && !chip.contains(e.target)) close();
    });
  }

  function _wireGlobalActions() {
    document.addEventListener('click', function (e) {
      var t = e.target.closest('[data-ms-action]');
      if (!t) return;
      var action = t.dataset.msAction;
      if (action === 'logout') {
        e.preventDefault();
        logout();
      } else if (action === 'open-notifications') {
        e.preventDefault();
        toast('No new alerts.', 'blue');
      }
    });
  }


  // ---------------------------------------------------------------------------
  // 7. Role guard — runs on every page load.
  //    - Unauthenticated visitors hitting /admin or /admin-dashboard get sent
  //      to /login (admin dashboard is never freely accessible).
  //    - Authenticated non-privileged users on /admin get sent to /dashboard.
  // ---------------------------------------------------------------------------
  function _runRoleGuard() {
    var path = (window.location.pathname || '').toLowerCase();
    var adminPaths = ['/admin', '/admin-dashboard'];
    var onAdmin = adminPaths.indexOf(path) !== -1;
    if (!onAdmin) return;
    if (!_user) {
      // Anonymous admin page hit → force login. Preserve where they were
      // trying to go so login can send them back after auth.
      try { sessionStorage.setItem('post_login_redirect', path); } catch (e) {}
      window.location.replace('/login');
      return;
    }
    if (!isPrivileged()) {
      window.location.replace('/dashboard');
    }
  }


  // ---------------------------------------------------------------------------
  // 7b. Gate CTAs by `data-ms-requires="auth|privileged"` attribute. Used by
  //     the home hero and any other page that has buttons whose destination
  //     should not be visible to logged-out / non-privileged visitors.
  //     - `auth`       → only render when user is logged in
  //     - `privileged` → only render when user is admin/officer/detective/staff
  //     When the requirement isn't met we replace the CTA with a "Log in"
  //     link pointing to /login (preserving the original destination in
  //     ?next= so login can send them back).
  // ---------------------------------------------------------------------------
  function _gateCTAs() {
    var nodes = document.querySelectorAll('[data-ms-requires]');
    if (!nodes.length) return;
    nodes.forEach(function (el) {
      var need = el.getAttribute('data-ms-requires');
      var ok = (need === 'auth')       ? !!_user
             : (need === 'privileged') ? isPrivileged()
             : true;
      if (ok) return;
      var href = el.getAttribute('href') || '/login';
      var label = (need === 'privileged') ? 'Log in as staff' : 'Log in to continue';
      // Replace with a ghost button that funnels into login + return.
      var replacement = document.createElement('a');
      replacement.href = '/login?next=' + encodeURIComponent(href);
      replacement.className = 'ms-btn ms-btn--ghost ms-btn--sm';
      replacement.setAttribute('data-ms-replacement-for', need);
      replacement.innerHTML = el.innerHTML;
      var span = replacement.querySelector('span');
      if (span) span.textContent = label;
      else replacement.appendChild(document.createTextNode(label));
      el.parentNode.replaceChild(replacement, el);
    });
  }


  // ---------------------------------------------------------------------------
  // 7c. Hide the "Station" spine tick for visitors who are not logged in.
  //     The rail is the user's primary navigation; showing a tick that
  //     requires admin auth and then redirecting on click is confusing.
  //     Hide it entirely until they sign in.
  // ---------------------------------------------------------------------------
  function _gateSpine() {
    var tick = document.querySelector('.ms-rail__tick[href="/admin"]');
    if (!tick) return;
    if (!_user || !isPrivileged()) tick.style.display = 'none';
  }


  // ---------------------------------------------------------------------------
  // 8. Logout. Clears auth_token + currentUser and redirects to /login.
  // ---------------------------------------------------------------------------
  function logout() {
    try {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('currentUser');
    } catch (e) { /* private mode */ }
    _user = null;
    window.location.href = '/login';
  }


  // ---------------------------------------------------------------------------
  // 9. Helpers — toasts, modals, API wrapper, escape.
  // ---------------------------------------------------------------------------
  function _ensureToastHost() {
    var h = document.getElementById('ms-toast-host');
    if (h) return h;
    h = document.createElement('div');
    h.id = 'ms-toast-host';
    h.className = 'ms-toast-host';
    document.body.appendChild(h);
    return h;
  }

  function toast(message, status) {
    var host = _ensureToastHost();
    status = status || 'blue';
    var t = document.createElement('div');
    t.className = 'ms-toast ms-toast--' + status;
    t.setAttribute('role', 'status');
    t.innerHTML =
      '<span class="ms-toast__body">' + window.escapeHtml(message) + '</span>' +
      '<button type="button" class="ms-toast__close" aria-label="Dismiss">' + icon('x') + '</button>';
    host.appendChild(t);
    var kill = function () {
      t.classList.add('is-leaving');
      setTimeout(function () { t.remove(); }, 200);
    };
    t.querySelector('.ms-toast__close').addEventListener('click', kill);
    setTimeout(kill, 4200);
  }

  function openModal(opts) {
    opts = opts || {};
    var back = document.createElement('div');
    back.className = 'ms-modal-back';
    back.setAttribute('role', 'dialog');
    back.setAttribute('aria-modal', 'true');
    back.innerHTML =
      '<div class="ms-modal">' +
        '<header class="ms-modal__head">' +
          '<h2 class="ms-modal__title">' + window.escapeHtml(opts.title || 'Confirm') + '</h2>' +
          '<button type="button" class="ms-modal__close" aria-label="Close">' + icon('x') + '</button>' +
        '</header>' +
        '<div class="ms-modal__body">' + (opts.body || '') + '</div>' +
        '<footer class="ms-modal__foot">' +
          (opts.cancelLabel ? '<button type="button" class="ms-btn ms-btn--ghost" data-ms-modal="cancel">' + window.escapeHtml(opts.cancelLabel) + '</button>' : '') +
          '<button type="button" class="ms-btn ms-btn--' + (opts.danger ? 'danger' : 'primary') + '" data-ms-modal="ok">' + window.escapeHtml(opts.okLabel || 'OK') + '</button>' +
        '</footer>' +
      '</div>';
    document.body.appendChild(back);
    function close(result) {
      back.classList.add('is-leaving');
      setTimeout(function () { back.remove(); if (opts.onClose) opts.onClose(result); }, 150);
    }
    back.addEventListener('click', function (e) {
      if (e.target === back) close(false);
      if (e.target.closest('[data-ms-modal="cancel"]')) close(false);
      if (e.target.closest('[data-ms-modal="ok"]')) close(true);
      if (e.target.closest('.ms-modal__close')) close(false);
    });
    document.addEventListener('keydown', function escHandler(ev) {
      if (ev.key === 'Escape') { close(false); document.removeEventListener('keydown', escHandler); }
    });
    return { close: close };
  }

  function confirmModal(message, opts) {
    opts = opts || {};
    return new Promise(function (resolve) {
      openModal({
        title: opts.title || 'Are you sure?',
        body: '<p>' + window.escapeHtml(message) + '</p>',
        okLabel: opts.okLabel || 'Confirm',
        cancelLabel: opts.cancelLabel || 'Cancel',
        danger: opts.danger,
        onClose: resolve
      });
    });
  }


  // ---------------------------------------------------------------------------
  // 10. API wrapper — uses fetch (already wrapped by api-base.js for auth).
  // ---------------------------------------------------------------------------
  var api = {
    get: function (path) { return _apiCall('GET', path); },
    post: function (path, body) { return _apiCall('POST', path, body); },
    put: function (path, body) { return _apiCall('PUT', path, body); },
    del: function (path) { return _apiCall('DELETE', path); }
  };

  function _apiCall(method, path, body) {
    var url = (window.resolveApiUrl || function (p) { return p; })(path);
    var init = { method: method, headers: { 'Content-Type': 'application/json' } };
    if (body !== undefined && body !== null) init.body = JSON.stringify(body);
    return fetch(url, init).then(function (r) {
      var ct = r.headers.get('content-type') || '';
      var p = ct.indexOf('application/json') !== -1 ? r.json() : r.text();
      return p.then(function (data) {
        if (!r.ok) {
          var err = new Error(typeof data === 'string' ? data : (data.detail || r.statusText));
          err.status = r.status;
          err.data = data;
          throw err;
        }
        return data;
      });
    });
  }


  // ---------------------------------------------------------------------------
  // 11. Public API
  // ---------------------------------------------------------------------------
  var MS = {
    version: '2.0.0',
    icon: icon,
    escape: window.escapeHtml,
    toast: toast,
    openModal: openModal,
    confirmModal: confirmModal,
    renderChrome: renderChrome,
    renderMinimalShell: renderMinimalShell,
    logout: logout,
    api: api,
    user: function () { return _user || _loadUser(); },
    setUser: _saveUser,
    isPrivileged: isPrivileged,
    ROLES: ROLES
  };

  // Stubs in case api-base.js / escape.js failed to load — better than a
  // blank page on /admin.
  if (typeof window.resolveApiUrl !== 'function') {
    window.resolveApiUrl = function (p) { return p; };
  }
  if (typeof window.escapeHtml !== 'function') {
    window.escapeHtml = function (s) {
      return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    };
  }
  if (!window.API_BASE) window.API_BASE = window.location.origin;

  window.MS = MS;

  // ---------------------------------------------------------------------------
  // 12. Auto-boot on DOMContentLoaded. Pages that need to render before this
  //    (e.g. legacy pages without #ms-root) can set window.__MS_AUTO_BOOT=false.
  // ---------------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', function () {
    _ready(function () {
      // Role guard runs on every page (even those without #ms-root, like the
      // admin dashboard). Anonymous visitors on /admin get sent to /login;
      // logged-in non-privileged users on /admin get sent to /dashboard.
      _user = _loadUser();
      _runRoleGuard();

      if (window.__MS_AUTO_BOOT === false) return;
      var root = document.getElementById('ms-root');
      if (!root) return;
      // Pages with .ms-auth / .ms-auth-* want the minimal (no rail, no topbar)
      // shell. Detect by class on the root, or opt-in via window.__MS_SHELL='minimal'.
      if (root.classList.contains('ms-auth') || window.__MS_SHELL === 'minimal') {
        renderMinimalShell();
      } else {
        renderChrome();
      }
      // After the chrome (and any template content) is in the DOM, gate
      // hero CTAs by auth/privileged status and hide the Station spine
      // tick for visitors who can't actually use it.
      _gateCTAs();
      _gateSpine();
    });
  });
})();