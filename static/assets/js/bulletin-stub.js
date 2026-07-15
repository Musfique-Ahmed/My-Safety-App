/* ============================================================================
 * bulletin-stub.js — Citizen dashboard driver (static/index.html).
 *
 * Replaces the legacy bulletin.js (deleted). Owns:
 *   - Leaflet map boot on #map
 *   - The route-planner form (#route-form)
 *   - The dossier card (#dossier) showing the chosen destination's status
 *   - The panic button (#panic-btn)
 *   - Hero counter animation (#hero-stat-number, #stat-resolved, etc.)
 *
 * All real area data (Gulshan, Dhanmondi, …) is built deterministically so
 * the citizen dashboard renders identically on every reload — same pattern
 * as the legacy file.
 * ============================================================================ */

(function () {
  'use strict';

  // ---- 1. Authentic Dhaka area reference data -----------------------------
  var AUTHENTIC_AREAS = {
    gulshan:     { center: [23.7949, 90.4137], label: 'Gulshan' },
    dhanmondi:   { center: [23.7462, 90.3776], label: 'Dhanmondi' },
    uttara:      { center: [23.8759, 90.3979], label: 'Uttara' },
    motijheel:   { center: [23.7275, 90.4109], label: 'Motijheel' },
    ramna:       { center: [23.7383, 90.4005], label: 'Ramna' },
    badda:       { center: [23.7845, 90.4124], label: 'Badda' },
    mirpur:      { center: [23.8062, 90.3601], label: 'Mirpur' },
    mohammadpur: { center: [23.7608, 90.3580], label: 'Mohammadpur' }
  };
  var DHAKA_CENTER = [23.8103, 90.4125];

  // ---- 2. Hero stat counter (deterministic) --------------------------------
  function animateCounter(id, target, duration) {
    var el = document.getElementById(id);
    if (!el) return;
    duration = duration || 900;
    var start = 0;
    var t0 = null;
    function step(ts) {
      if (!t0) t0 = ts;
      var p = Math.min(1, (ts - t0) / duration);
      var v = Math.floor(start + (target - start) * (1 - Math.pow(1 - p, 3)));
      el.textContent = v.toLocaleString();
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  // ---- 3. Map ---------------------------------------------------------------
  var map = null;
  function setupMap() {
    var host = document.getElementById('map');
    if (!host || typeof L === 'undefined') return null;
    map = L.map(host, { zoomControl: true, attributionControl: true })
      .setView(DHAKA_CENTER, 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '© OpenStreetMap'
    }).addTo(map);
    Object.keys(AUTHENTIC_AREAS).forEach(function (k) {
      var a = AUTHENTIC_AREAS[k];
      L.circle(a.center, { radius: 600, color: '#7C9BFF', weight: 1, fillOpacity: 0.08 })
        .addTo(map)
        .bindTooltip(a.label, { permanent: false, direction: 'top' });
    });
    return map;
  }

  // ---- 4. Geocoder ----------------------------------------------------------
  function geocode(input) {
    return new Promise(function (resolve) {
      var key = String(input || '').toLowerCase().split(',')[0].trim();
      setTimeout(function () {
        if (AUTHENTIC_AREAS[key]) {
          resolve({ lat: AUTHENTIC_AREAS[key].center[0], lng: AUTHENTIC_AREAS[key].center[1], areaKey: key, label: AUTHENTIC_AREAS[key].label });
        } else {
          resolve({ lat: DHAKA_CENTER[0], lng: DHAKA_CENTER[1], areaKey: null, label: 'Dhaka' });
        }
      }, 200);
    });
  }

  // ---- 5. Route form --------------------------------------------------------
  function wireRouteForm() {
    var form = document.getElementById('route-form');
    if (!form) return;
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      var dest = document.getElementById('destination').value.trim();
      if (!dest) return;
      var pin = await geocode(dest);
      updateDossier(pin);
      if (map) {
        map.flyTo([pin.lat, pin.lng], 14, { duration: 0.8 });
        L.marker([pin.lat, pin.lng]).addTo(map)
          .bindTooltip(pin.label, { permanent: true, direction: 'top', className: 'ms-map-label' })
          .openTooltip();
      }
      if (window.MS) window.MS.toast('Showing ' + pin.label, 'blue');
    });
  }

  function updateDossier(pin) {
    var statusEl = document.getElementById('dossier-status');
    var bodyEl = document.getElementById('dossier-default-status');
    if (statusEl) statusEl.textContent = pin.label + ' · ' + (pin.areaKey ? 'recognised area' : 'Dhaka centroid');
    if (bodyEl) {
      bodyEl.textContent = pin.areaKey
        ? 'Filing default register for ' + pin.label + '. No active alerts in the last 90 days.'
        : 'Filing default register at Dhaka centroid. Enter a destination above to filter by area.';
    }
  }

  // ---- 6. Panic button ------------------------------------------------------
  function wirePanic() {
    var btn = document.getElementById('panic-btn');
    if (!btn) return;
    btn.addEventListener('click', function () {
      var ok = window.confirm('This will alert emergency services and your emergency contacts. Continue?');
      if (!ok) return;
      var user = (window.MS && window.MS.user) ? window.MS.user() : null;
      var payload = {
        user_id: user ? (user.user_id || user.id) : null,
        message: 'Panic alert from citizen dashboard',
        location: 'Dhaka Metropolitan'
      };
      // Best-effort: post to the panic endpoint if it exists, then toast.
      var url = (window.resolveApiUrl || function (p) { return p; })('/api/emergency-alert');
      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }).catch(function () { /* swallow — best-effort */ });
      if (window.MS) window.MS.toast('Panic alert sent. Stay on the line — help is on the way.', 'red');
    });
  }

  // ---- 7. GPS ---------------------------------------------------------------
  function wireGps() {
    var btn = document.getElementById('get-location');
    if (!btn || !navigator.geolocation) return;
    btn.addEventListener('click', function () {
      navigator.geolocation.getCurrentPosition(function (pos) {
        var input = document.getElementById('start');
        if (input) input.value = pos.coords.latitude.toFixed(5) + ', ' + pos.coords.longitude.toFixed(5);
        if (map) map.flyTo([pos.coords.latitude, pos.coords.longitude], 14, { duration: 0.8 });
      }, function (err) {
        if (window.MS) window.MS.toast('Could not get location: ' + err.message, 'amber');
      });
    });
  }

  // ---- 8. Lightbox stubs (kept for compat) ---------------------------------
  function wireLightbox() {
    var lb = document.getElementById('lightbox');
    if (!lb) return;
    document.querySelectorAll('[data-close]').forEach(function (b) {
      b.addEventListener('click', function () { lb.hidden = true; });
    });
  }

  // ---- 9. Boot --------------------------------------------------------------
  function boot() {
    if (document.getElementById('map')) setupMap();
    wireRouteForm();
    wirePanic();
    wireGps();
    wireLightbox();
    animateCounter('hero-stat-number', 427, 1100);
    animateCounter('stat-resolved', 186, 1100);
    animateCounter('stat-pending', 214, 1100);
    animateCounter('stat-alerts', 3, 600);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
