/* ============================================================================
 * bulletin.js — driver for static/index.html ("The Case-File Bulletin")
 *
 * Public API: window.MS.<field>.  No globals leak except:
 *   - MS       (this file)
 *   - lucide   is NOT loaded here — replaced by tag-glyph CSS components
 *   - window.fetch is wrapped by api-base.js (auth header injection)
 * ============================================================================ */

(function () {
  'use strict';

  // -------------------------------------------------------------------------
  // 0. Reference api-base.js / escape.js (loaded before this script).
  //    resolveApiUrl + escapeHtml are added to window by those files.
  // -------------------------------------------------------------------------
  var escapeHtml = window.escapeHtml || function (s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  };


  // -------------------------------------------------------------------------
  // 1. Authentic Dhaka area + sub-area reference data (kept verbatim).
  // -------------------------------------------------------------------------
  var AUTHENTIC_AREAS = {
    gulshan:     { center: [23.7949, 90.4137],
      subareas: [
        { name: 'Gulshan-1', lat: 23.7806, lng: 90.4167 },
        { name: 'Gulshan-2', lat: 23.7925, lng: 90.4078 },
        { name: 'Banani',    lat: 23.7975, lng: 90.4100 }
      ]},
    dhanmondi:   { center: [23.7462, 90.3776],
      subareas: [
        { name: 'Shankar',       lat: 23.7432, lng: 90.3698 },
        { name: 'Dhanmondi-15',  lat: 23.7475, lng: 90.3742 },
        { name: 'Abahani Field', lat: 23.7510, lng: 90.3770 }
      ]},
    uttara:      { center: [23.8759, 90.3979],
      subareas: [
        { name: 'Sector 4',  lat: 23.8765, lng: 90.3950 },
        { name: 'Sector 7',  lat: 23.8800, lng: 90.4000 },
        { name: 'Sector 10', lat: 23.8850, lng: 90.4020 }
      ]},
    motijheel:   { center: [23.7275, 90.4109],
      subareas: [
        { name: 'Motijheel Colony', lat: 23.7280, lng: 90.4120 },
        { name: 'Dilkusha',         lat: 23.7300, lng: 90.4090 }
      ]},
    ramna:       { center: [23.7383, 90.4005],
      subareas: [
        { name: 'Ramna Park',    lat: 23.7365, lng: 90.4012 },
        { name: 'Bangla Motor',  lat: 23.7410, lng: 90.3980 }
      ]},
    badda:       { center: [23.7845, 90.4124],
      subareas: [
        { name: 'Middle Badda', lat: 23.7830, lng: 90.4150 },
        { name: 'North Badda',  lat: 23.7860, lng: 90.4130 }
      ]},
    mirpur:      { center: [23.8062, 90.3601],
      subareas: [
        { name: 'Mirpur-1',  lat: 23.8030, lng: 90.3530 },
        { name: 'Mirpur-10', lat: 23.8100, lng: 90.3620 },
        { name: 'Pallabi',   lat: 23.8150, lng: 90.3650 }
      ]},
    mohammadpur: { center: [23.7608, 90.3580],
      subareas: [
        { name: 'Mohammadpur Bus Stand', lat: 23.7580, lng: 90.3560 },
        { name: 'Adabor',                lat: 23.7650, lng: 90.3600 },
        { name: 'Town Hall',             lat: 23.7620, lng: 90.3540 }
      ]}
  };

  // -------------------------------------------------------------------------
  // 2. Geocoding (kept verbatim — accepts area name, returns coords).
  // -------------------------------------------------------------------------
  function geocodeDestination(destination) {
    return new Promise(function (resolve) {
      var key = String(destination || '').toLowerCase().split(',')[0].trim();
      setTimeout(function () {
        if (AUTHENTIC_AREAS[key]) {
          resolve({ lat: AUTHENTIC_AREAS[key].center[0],
                    lng: AUTHENTIC_AREAS[key].center[1],
                    areaKey: key });
        } else {
          // Default to Dhaka centroid; flagged as "unknown" in the dossier head
          resolve({ lat: 23.7770, lng: 90.3952, areaKey: null });
        }
      }, 400);
    });
  }


  // -------------------------------------------------------------------------
  // 3. Crime register (deterministic for visual stability — not Math.random,
  //    because we want a single month-of-data set: 427 incidents baseline).
  // -------------------------------------------------------------------------
  var INVESTIGATION_STAGES = [
    'FIR Registered', 'Crime Scene', 'Evidence Collection',
    'Suspect ID', 'Interrogation', 'Case Filed', 'Court Trial'
  ];
  var CRIME_TYPES = [
    'Robbery', 'Assault', 'Theft', 'Arson', 'Vandalism',
    'Pickpocketing', 'Homicide'
  ];
  var PRIORITY_LEVELS = ['normal', 'elevated', 'high'];

  // Tiny seeded RNG so the dossier renders identically on every reload.
  function _seeded(seed) {
    var x = seed % 2147483647;
    if (x <= 0) x += 2147483646;
    return function () {
      x = (x * 16807) % 2147483647;
      return (x - 1) / 2147483646;
    };
  }

  function buildRegister() {
    var rng = _seeded(20260714);
    var entries = [];
    var totalIncidents = 0;
    var monthTotal = 427; // matches the hero stat

    Object.keys(AUTHENTIC_AREAS).forEach(function (areaKey) {
      var area = AUTHENTIC_AREAS[areaKey];
      area.subareas.forEach(function (sub) {
        // 5..10 incidents per sub-area
        var count = 5 + Math.floor(rng() * 6);
        var solved = [];
        var unsolved = [];
        for (var i = 0; i < count; i++) {
          var isSolved = rng() < 0.32;
          var dayOffset = 1 + Math.floor(rng() * 90);
          var d = new Date();
          d.setDate(d.getDate() - dayOffset);
          var record = {
            id: areaKey + '-' + sub.name.replace(/\W+/g, '') + '-' + i,
            name: sub.name,
            area: areaKey,
            lat: sub.lat + (rng() - 0.5) * 0.002,
            lng: sub.lng + (rng() - 0.5) * 0.002,
            title: CRIME_TYPES[Math.floor(rng() * CRIME_TYPES.length)],
            date: d.toISOString().split('T')[0],
            priority: PRIORITY_LEVELS[Math.floor(rng() * PRIORITY_LEVELS.length)],
            details: 'Incident: ' + CRIME_TYPES[Math.floor(rng() * CRIME_TYPES.length)] +
                     '. Near ' + sub.name + ', ' +
                     areaKey.charAt(0).toUpperCase() + areaKey.slice(1) + '.',
            resolved: isSolved
          };
          if (isSolved) {
            solved.push(record);
          } else {
            record.stage = INVESTIGATION_STAGES[Math.floor(rng() * INVESTIGATION_STAGES.length)];
            unsolved.push(record);
          }
          totalIncidents++;
        }
        entries.push({
          name: sub.name,
          area: areaKey,
          lat: sub.lat,
          lng: sub.lng,
          solved: solved,
          unsolved: unsolved
        });
      });
    });

    return { entries: entries, monthTotal: monthTotal, allTotal: totalIncidents };
  }

  var register = buildRegister();


  // -------------------------------------------------------------------------
  // 4. Distance helper (haversine, km)
  // -------------------------------------------------------------------------
  function getDistance(lat1, lon1, lat2, lon2) {
    var R = 6371;
    var dLat = (lat2 - lat1) * Math.PI / 180;
    var dLon = (lon2 - lon1) * Math.PI / 180;
    var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }


  // -------------------------------------------------------------------------
  // 5. Map setup — Leaflet + heat + popups.
  // -------------------------------------------------------------------------
  function setupMap() {
    var dhakaCoords = [23.8103, 90.4125];
    var map = L.map('map').setView(dhakaCoords, 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '© OpenStreetMap'
    }).addTo(map);
    return map;
  }


  // -------------------------------------------------------------------------
  // 6. Popup HTML builder — uses new CSS classes, escapeHtml on all text.
  // -------------------------------------------------------------------------
  function buildPopupHtml(area) {
    var areaLabel = area.area.charAt(0).toUpperCase() + area.area.slice(1);
    var html = '<div class="popup-title">' + escapeHtml(area.name) + '</div>';
    html    += '<div class="popup-meta">' + escapeHtml(areaLabel) + ' · '
            + (area.unsolved.length + area.solved.length) + ' INCIDENTS · LAST 90 D</div>';

    if (area.unsolved.length > 0) {
      html += '<div class="popup-section"><h5>OPEN CASES · ' + area.unsolved.length + '</h5><ul>';
      area.unsolved.forEach(function (c) {
        html += '<li>' + escapeHtml(c.title) + ' · <span style="color:var(--ink-faded)">'
             + escapeHtml(c.date) + '</span> · '
             + escapeHtml(c.stage) + '</li>';
      });
      html += '</ul></div>';
    } else {
      html += '<div class="popup-section"><h5>OPEN CASES · 0</h5>'
           +  '<div style="color:var(--ink-faded); font-style:italic">All clear in last 90 days.</div></div>';
    }

    if (area.solved.length > 0) {
      html += '<div class="popup-section"><h5>RESOLVED · ' + area.solved.length + '</h5><ul>';
      area.solved.forEach(function (c) {
        html += '<li class="resolved">' + escapeHtml(c.title) + ' · '
             +  escapeHtml(c.date) + '</li>';
      });
      html += '</ul></div>';
    }
    return html;
  }


  // -------------------------------------------------------------------------
  // 7. Render dossier (Local Register) under the map.
  //    Sorted by unsolved count desc, then by name asc.
  // -------------------------------------------------------------------------
  function renderDossier(filteredAreas, center) {
    var el = document.getElementById('dossier');
    if (!el) return;

    var sorted = filteredAreas.slice().sort(function (a, b) {
      var u = b.unsolved.length - a.unsolved.length;
      if (u !== 0) return u;
      return a.name.localeCompare(b.name);
    });

    var totalOpen = 0;
    var rows = sorted.map(function (area) {
      totalOpen += area.unsolved.length;
      var isDanger = area.unsolved.length >= 8;
      var priority = area.unsolved.length >= 10 ? 'HIGH'
                   : area.unsolved.length >= 5 ? 'ELEVATED' : 'NORMAL';
      var stageLabel = area.unsolved.length > 0
        ? area.unsolved[0].stage || 'FIR REGISTERED'
        : '—';
      return ''
        + '<article class="dossier__row' + (isDanger ? ' is-danger' : '') + '">'
        +   '<span class="tag">A</span>'
        +   '<div>'
        +     '<div class="name">' + escapeHtml(area.name) + '</div>'
        +     '<div class="area">' + escapeHtml(
              area.area.charAt(0).toUpperCase() + area.area.slice(1)) + '</div>'
        +   '</div>'
        +   '<div>'
        +     '<span class="count">' + area.unsolved.length + '</span>'
        +     '<span class="count-label">OPEN</span>'
        +   '</div>'
        +   '<div class="stage">' + escapeHtml(priority + ' · ' + stageLabel) + '</div>'
        + '</article>';
    }).join('');

    el.innerHTML =
        '<div class="dossier__head">'
      +   '<span>ENTRY · LOCAL REGISTER</span>'
      +   '<span>' + sorted.length + ' ZONES · ' + totalOpen + ' OPEN INCIDENTS</span>'
      + '</div>'
      + '<div class="dossier__status">'
      +   'Centred on destination. Showing zones within 2.5&nbsp;km radius.'
      + '</div>'
      + rows;
  }


  // -------------------------------------------------------------------------
  // 8. Filter and re-render: heat layer + area markers + dossier.
  // -------------------------------------------------------------------------
  var layers = { markers: [], heat: null };

  function renderAt(centerLat, centerLng) {
    var map = window.__MS_MAP__;
    if (!map) return;

    // clear previous
    layers.markers.forEach(function (l) { map.removeLayer(l); });
    layers.markers = [];
    if (layers.heat) { map.removeLayer(layers.heat); layers.heat = null; }

    var nearby = [];
    var heatPoints = [];
    var RADIUS_KM = 2.5;

    register.entries.forEach(function (area) {
      var distance = getDistance(centerLat, centerLng, area.lat, area.lng);
      if (distance <= RADIUS_KM) {
        nearby.push(area);
        area.unsolved.forEach(function (c) {
          heatPoints.push([c.lat, c.lng, 1]);
        });
      }
    });

    map.setView([centerLat, centerLng], 14);

    if (heatPoints.length > 0) {
      layers.heat = L.heatLayer(heatPoints, {
        radius: 32, blur: 22, maxZoom: 16,
        gradient: { 0.0: '#6FA182', 0.5: '#B58A3D', 1.0: '#A23E2C' }
      }).addTo(map);
      layers.markers.push(layers.heat);

      nearby.forEach(function (area) {
        if (area.unsolved.length === 0) return;
        var m = L.marker([area.lat, area.lng], { keyboard: true, title: area.name })
          .addTo(map)
          .bindPopup(buildPopupHtml(area));
        layers.markers.push(m);
      });
    }

    // Status line in dossier head
    var statusEl = document.getElementById('dossier-status');
    if (statusEl) {
      statusEl.textContent = nearby.length > 0
        ? 'Showing ' + nearby.length + ' zones within ' + RADIUS_KM + ' km · '
          + heatPoints.length + ' incidents · Centred ' +
          centerLat.toFixed(4) + ', ' + centerLng.toFixed(4)
        : 'No recent crime zones within ' + RADIUS_KM + ' km.';
    }

    renderDossier(nearby, { lat: centerLat, lng: centerLng });
  }


  // -------------------------------------------------------------------------
  // 9. Hero stat counter (animated count-up from 0 to 427 over 1.4s).
  // -------------------------------------------------------------------------
  function animateCounter(el, target, durationMs) {
    if (!el) return;
    var start = 0;
    var t0 = null;
    function step(t) {
      if (t0 === null) t0 = t;
      var p = Math.min(1, (t - t0) / durationMs);
      var eased = 1 - Math.pow(1 - p, 3); // easeOutCubic
      var v = Math.round(start + (target - start) * eased);
      el.textContent = v;
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }


  // -------------------------------------------------------------------------
  // 10. Stamp the running timestamp into the registry header.
  // -------------------------------------------------------------------------
  function tickStamp() {
    var el = document.getElementById('reg-stamp');
    if (!el) return;
    var d = new Date();
    var months = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
    var pad = function (n) { return n < 10 ? '0' + n : '' + n; };
    var s =
      'REGISTERED '
      + pad(d.getDate()) + ' ' + months[d.getMonth()] + ' ' + d.getFullYear()
      + ' — ' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
    el.textContent = s;
  }


  // -------------------------------------------------------------------------
  // 11. Wire up form, geolocation, panic button.
  // -------------------------------------------------------------------------
  function wireForm() {
    var form = document.getElementById('route-form');
    var start = document.getElementById('start');
    var destination = document.getElementById('destination');
    var timeInput = document.getElementById('time');
    var age = document.getElementById('age');
    var gender = document.getElementById('gender');
    var geolocate = document.getElementById('get-location');
    var panic = document.getElementById('panic-btn');

    if (!form) return;

    // Auto-fill current time
    if (timeInput) {
      var now = new Date();
      timeInput.value =
        String(now.getHours()).padStart(2, '0') + ':' +
        String(now.getMinutes()).padStart(2, '0');
    }

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var destRaw = (destination.value || '').trim() || 'Dhaka';
      // Visual feedback
      var btn = form.querySelector('.btn-stamp');
      if (btn) {
        btn.textContent = '— LOCATING —';
      }
      geocodeDestination(destRaw).then(function (geo) {
        if (btn) btn.innerHTML = '<span class="btn-stamp__chevron">→</span> FIND SAFEST ROUTE';
        renderAt(geo.lat, geo.lng);
      });
    });

    if (geolocate) {
      geolocate.addEventListener('click', function () {
        if (!navigator.geolocation) {
          start.value = 'GEOLOCATION UNAVAILABLE';
          return;
        }
        start.value = '— LOCATING —';
        navigator.geolocation.getCurrentPosition(function (pos) {
          start.value = pos.coords.latitude.toFixed(4) + ', ' + pos.coords.longitude.toFixed(4);
          // Render immediately on current position
          renderAt(pos.coords.latitude, pos.coords.longitude);
        }, function () {
          start.value = 'PERMISSION DENIED';
        });
      });
    }

    if (panic) {
      panic.addEventListener('click', function () {
        // Stamp-style confirmation (not a modal — this is a register)
        if (window.confirm('Transmit PANIC alert to nearest station? This is irreversible.')) {
          // POST to /api/emergency-alert when available; for now, the visible
          // urgency is the button turning red (paper-ink stamp) per CSS.
          window.fetch(resolveApiUrl('/api/emergency-alert'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              destination: destination.value,
              time: timeInput.value,
              lat: null, lng: null
            })
          }).catch(function () { /* fire-and-forget */ });
        }
      });
    }
  }


  // -------------------------------------------------------------------------
  // 12. Boot.
  // -------------------------------------------------------------------------
  function boot() {
    window.__MS_MAP__ = setupMap();
    wireForm();

    var stat = document.getElementById('hero-stat-number');
    animateCounter(stat, register.monthTotal, 1400);

    // First render — centered on Dhaka centroid
    renderAt(23.7770, 90.3952);

    tickStamp();
    setInterval(tickStamp, 1000);

    // Expose for tests / future programmatic calls
    window.MS = {
      register: register,
      renderAt: renderAt,
      AUTHENTIC_AREAS: AUTHENTIC_AREAS
    };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
