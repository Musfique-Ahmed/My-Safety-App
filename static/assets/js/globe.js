/* ============================================================================
 * globe.js — Dhaka-anchored operations radar.
 *
 * Renders into <div class="ms-globe" id="ms-globe"></div>. The page must
 * include a call to MS.globe.mount('#ms-globe') (or rely on auto-mount when
 * the element is present on DOMContentLoaded).
 *
 * Visual: a luminous dark radar disc centred on Dhaka (≈23.81°N, 90.41°E).
 * On top of the disc we draw:
 *   - The Bangladesh landmass (stylised silhouette + graticule)
 *   - Six major districts as labelled markers
 *   - Hot-spot alert pulses in status colours
 *   - A slow rotating sweep arm (radar-style)
 *   - "DHAKA · 23.81° N · 90.41° E" label on the rim
 *
 * This is a pure 2D Canvas implementation — no WebGL, no three.js, no bundle
 * weight, no software-rendering dark frames. The dashboard stays alive even
 * on integrated graphics, headless Chromium, or offline.
 *
 * Three.js + three-globe was considered but dropped: the WebGL earth on
 * software rendering was nearly invisible, the bundle is ~600 KB, and the
 * safety subject isn't "the planet" — it's "what's happening around Dhaka".
 * A radar centred on the home city tells the story better.
 * ============================================================================ */

(function () {
  'use strict';

  // Default alert hot-spots (lat, lng, severity, label).
  // Coordinates are real Dhaka districts; severity drives colour only.
  var DEFAULT_HOTSPOTS = [
    { lat: 23.7949, lng: 90.4137, sev: 'red',   label: 'Gulshan' },
    { lat: 23.7462, lng: 90.3776, sev: 'amber', label: 'Dhanmondi' },
    { lat: 23.8759, lng: 90.3979, sev: 'green', label: 'Uttara' },
    { lat: 23.7275, lng: 90.4109, sev: 'amber', label: 'Motijheel' },
    { lat: 23.7383, lng: 90.4005, sev: 'blue',  label: 'Ramna' },
    { lat: 23.7845, lng: 90.4124, sev: 'red',   label: 'Badda' },
    { lat: 23.8062, lng: 90.3601, sev: 'blue',  label: 'Mirpur' },
    { lat: 23.7608, lng: 90.3580, sev: 'green', label: 'Mohammadpur' },
    { lat: 23.7510, lng: 90.3875, sev: 'amber', label: 'Tejgaon' }
  ];

  // Stylised Bangladesh landmass — a coarse but recognisable outline that
  // places Dhaka inside the silhouette. Coordinates are deliberately
  // exaggerated (it's a brand element, not a navigation chart).
  // Each entry is [lng, lat]; lat/lng are mapped to canvas via the same
  // projection as the hot-spots below.
  var LANDMASS = [
    [88.0, 26.0], [89.0, 26.2], [89.7, 25.8], [90.0, 25.5], [90.5, 25.0],
    [91.0, 24.5], [91.5, 24.0], [91.8, 23.5], [92.0, 23.0], [91.7, 22.5],
    [91.5, 22.0], [91.2, 21.7], [90.8, 21.8], [90.5, 22.0], [90.3, 22.3],
    [89.9, 22.5], [89.5, 22.3], [89.3, 22.7], [89.0, 22.0], [88.7, 21.7],
    [88.5, 22.0], [88.3, 22.5], [88.0, 23.0], [88.1, 23.7], [88.0, 24.5],
    [88.0, 26.0]
  ];

  var DHAKA_LAT = 23.8103;
  var DHAKA_LNG = 90.4125;

  // The canvas extent we map onto: roughly 6° around Dhaka, with the canvas
  // being a disc of maxR. lng/x scales by cos(lat) to keep proportions right.
  var LNG_SPAN = 6.0;
  var LAT_SPAN = 6.0;

  var REDUCED_MOTION = (typeof window !== 'undefined' && window.matchMedia)
    ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
    : false;

  function sevColor(sev) {
    return ({
      red:   '#EF4E5A',
      amber: '#F2A93B',
      green: '#3BCB8A',
      blue:  '#5B7CFA'
    })[sev] || '#5B7CFA';
  }

  // Map lat/lng to (x, y) inside a disc of radius maxR centred on Dhaka.
  function project(lat, lng, cx, cy, maxR) {
    var dLng = (lng - DHAKA_LNG) / LNG_SPAN;
    var dLat = (lat - DHAKA_LAT) / LAT_SPAN;
    var x = cx + dLng * maxR * Math.cos(DHAKA_LAT * Math.PI / 180);
    var y = cy - dLat * maxR;
    return { x: x, y: y };
  }

  // ---------------------------------------------------------------------------
  // Canvas radar — the default and only renderer. Dhaka-centred, with the
  // Bangladesh landmass, district markers, status pulses, sweep, and rim
  // label. Everything in one frame function.
  // ---------------------------------------------------------------------------
  function _renderCanvas(host, hotspots) {
    host.innerHTML = '';
    var size = Math.min(host.clientWidth || 560, host.clientHeight || 560);
    if (!size) size = 560;
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var canvas = document.createElement('canvas');
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    host.appendChild(canvas);
    var ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    var cx = size / 2;
    var cy = size / 2;
    var maxR = size * 0.42;
    var t0 = performance.now();
    var _rafStop = false;

    function frame(now) {
      if (_rafStop) return;
      var t = (now - t0) / 1000;
      ctx.clearRect(0, 0, size, size);

      // ---- Disc ----
      var discGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, maxR);
      discGrad.addColorStop(0,    '#3B6EC5');
      discGrad.addColorStop(0.5,  '#1F3870');
      discGrad.addColorStop(1,    '#0F1A35');
      ctx.fillStyle = discGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, maxR, 0, Math.PI * 2);
      ctx.fill();

      // Outer rim — strong accent
      ctx.strokeStyle = '#7C9BFF';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(cx, cy, maxR, 0, Math.PI * 2);
      ctx.stroke();
      ctx.strokeStyle = 'rgba(124, 155, 255, 0.45)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(cx, cy, maxR + 6, 0, Math.PI * 2);
      ctx.stroke();

      // ---- Concentric range rings (bright cyan-blue) ----
      ctx.strokeStyle = 'rgba(180, 210, 255, 0.55)';
      ctx.lineWidth = 1;
      for (var i = 1; i <= 4; i++) {
        ctx.beginPath();
        ctx.arc(cx, cy, (maxR * i) / 4, 0, Math.PI * 2);
        ctx.stroke();
      }

      // ---- Crosshair (clearly visible) ----
      ctx.strokeStyle = 'rgba(180, 210, 255, 0.35)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx - maxR, cy); ctx.lineTo(cx + maxR, cy);
      ctx.moveTo(cx, cy - maxR); ctx.lineTo(cx, cy + maxR);
      ctx.stroke();

      // ---- Compass ticks ----
      ctx.fillStyle = 'rgba(166, 176, 197, 0.55)';
      ctx.font = '600 10px JetBrains Mono, monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('N', cx, cy - maxR + 12);
      ctx.fillText('S', cx, cy + maxR - 12);
      ctx.fillText('E', cx + maxR - 12, cy);
      ctx.fillText('W', cx - maxR + 12, cy);

      // ---- Bangladesh landmass silhouette ----
      ctx.save();
      ctx.beginPath();
      var started = false;
      LANDMASS.forEach(function (pt) {
        var p = project(pt[1], pt[0], cx, cy, maxR);
        if (!started) { ctx.moveTo(p.x, p.y); started = true; }
        else { ctx.lineTo(p.x, p.y); }
      });
      ctx.closePath();
      var landGrad = ctx.createLinearGradient(cx, cy - maxR, cx, cy + maxR);
      landGrad.addColorStop(0, 'rgba(124, 155, 255, 0.18)');
      landGrad.addColorStop(1, 'rgba(91, 124, 250, 0.10)');
      ctx.fillStyle = landGrad;
      ctx.fill();
      ctx.strokeStyle = 'rgba(124, 155, 255, 0.35)';
      ctx.lineWidth = 1.2;
      ctx.stroke();
      ctx.restore();

      // ---- Major rivers (stylised hairlines for visual richness) ----
      ctx.save();
      ctx.strokeStyle = 'rgba(124, 155, 255, 0.20)';
      ctx.lineWidth = 0.8;
      // Padma + Meghna + Jamuna — three quick curves through Bangladesh.
      var rivers = [
        [[88.5, 25.0], [89.5, 24.5], [90.0, 24.0], [90.5, 23.5], [91.0, 23.0]],
        [[91.0, 25.0], [90.5, 24.5], [90.2, 24.2], [90.5, 23.8], [91.0, 23.5]],
        [[89.0, 23.0], [89.7, 23.2], [90.3, 23.0], [90.8, 22.7], [91.2, 22.5]]
      ];
      rivers.forEach(function (r) {
        ctx.beginPath();
        r.forEach(function (pt, i) {
          var p = project(pt[1], pt[0], cx, cy, maxR);
          if (i === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y);
        });
        ctx.stroke();
      });
      ctx.restore();

      // ---- District labels (subtle, behind hot-spots) ----
      ctx.font = '500 10px Inter, system-ui, sans-serif';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      hotspots.forEach(function (h) {
        var p = project(h.lat, h.lng, cx, cy, maxR);
        // Draw small dot + label offset.
        ctx.fillStyle = 'rgba(166, 176, 197, 0.65)';
        ctx.beginPath();
        ctx.arc(p.x, p.y, 1.8, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = 'rgba(166, 176, 197, 0.55)';
        ctx.fillText(h.label, p.x + 6, p.y - 8);
      });

      // ---- Sweep arm (radar-style rotating beam) ----
      if (!REDUCED_MOTION) {
        var sweepAngle = (t * 0.6) % (Math.PI * 2);
        var sweepGrad = ctx.createConicGradient
          ? ctx.createConicGradient(sweepAngle, cx, cy)
          : null;
        if (sweepGrad) {
          sweepGrad.addColorStop(0,    'rgba(124, 155, 255, 0.32)');
          sweepGrad.addColorStop(0.08, 'rgba(124, 155, 255, 0.10)');
          sweepGrad.addColorStop(0.15, 'rgba(124, 155, 255, 0.00)');
          sweepGrad.addColorStop(1,    'rgba(124, 155, 255, 0.00)');
          ctx.save();
          ctx.beginPath();
          ctx.arc(cx, cy, maxR, 0, Math.PI * 2);
          ctx.clip();
          ctx.fillStyle = sweepGrad;
          ctx.fillRect(cx - maxR, cy - maxR, maxR * 2, maxR * 2);
          ctx.restore();
        }
      }

      // ---- Hot-spot pulses (status-coloured) ----
      hotspots.forEach(function (h, i) {
        var p = project(h.lat, h.lng, cx, cy, maxR);
        var pulse = 0.5 + 0.5 * Math.sin(t * 1.8 + i * 0.7);
        var r = 8 + 4 * pulse;
        var color = sevColor(h.sev);
        // Glow halo
        var g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * 4);
        g.addColorStop(0, color);
        g.addColorStop(0.4, hexToRgba(color, 0.25));
        g.addColorStop(1, hexToRgba(color, 0));
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r * 4, 0, Math.PI * 2);
        ctx.fill();
        // Solid core
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r * 0.45, 0, Math.PI * 2);
        ctx.fill();
        // Ring
        ctx.strokeStyle = hexToRgba(color, 0.6);
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
        ctx.stroke();
      });

      // ---- Dhaka hub (the brightest point on the radar) ----
      var dhaka = project(DHAKA_LAT, DHAKA_LNG, cx, cy, maxR);
      var hubPulse = 0.5 + 0.5 * Math.sin(t * 1.6);
      var hubR = 16 + hubPulse * 6;
      var hubGrad = ctx.createRadialGradient(dhaka.x, dhaka.y, 0, dhaka.x, dhaka.y, hubR * 4);
      hubGrad.addColorStop(0,    'rgba(255, 255, 255, 0.45)');
      hubGrad.addColorStop(0.15, 'rgba(124, 155, 255, 0.55)');
      hubGrad.addColorStop(0.5,  'rgba(124, 155, 255, 0.20)');
      hubGrad.addColorStop(1,    'rgba(124, 155, 255, 0)');
      ctx.fillStyle = hubGrad;
      ctx.beginPath();
      ctx.arc(dhaka.x, dhaka.y, hubR * 4, 0, Math.PI * 2);
      ctx.fill();
      // Hub core
      ctx.fillStyle = '#FFFFFF';
      ctx.beginPath();
      ctx.arc(dhaka.x, dhaka.y, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#7C9BFF';
      ctx.beginPath();
      ctx.arc(dhaka.x, dhaka.y, 3, 0, Math.PI * 2);
      ctx.fill();
      // Hub label
      ctx.fillStyle = '#F2F4F8';
      ctx.font = '700 11px Inter, system-ui, sans-serif';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillText('DHAKA', dhaka.x + 10, dhaka.y - 12);
      ctx.fillStyle = 'rgba(166, 176, 197, 0.75)';
      ctx.font = '500 9px JetBrains Mono, monospace';
      ctx.fillText('23.81° N · 90.41° E', dhaka.x + 10, dhaka.y + 2);

      // ---- Rim caption (drawn INSIDE the disc, near the top edge, so the
      // HTML-level .ms-globe__callout overlay (top-right) can't clip it).
      ctx.fillStyle = 'rgba(242, 244, 248, 0.92)';
      ctx.font = '700 15px Inter, system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'alphabetic';
      ctx.fillText('DHAKA METROPOLITAN', cx, cy - maxR + 22);
      ctx.fillStyle = 'rgba(166, 176, 197, 0.75)';
      ctx.font = '500 10px JetBrains Mono, monospace';
      ctx.fillText('LIVE OPERATIONS RADAR', cx, cy - maxR + 36);

      // ---- Status pills inside the disc near the bottom edge, so the
      // HTML-level .ms-globe__legend overlay (bottom-left) can't clip them.
      var counts = { red: 0, amber: 0, green: 0, blue: 0 };
      hotspots.forEach(function (h) { counts[h.sev] = (counts[h.sev] || 0) + 1; });
      var pillY = cy + maxR - 14;
      var pills = [
        { c: '#EF4E5A', label: counts.red + ' active' },
        { c: '#F2A93B', label: counts.amber + ' pending' },
        { c: '#3BCB8A', label: counts.green + ' cleared' },
        { c: '#5B7CFA', label: counts.blue + ' info' }
      ];
      var pillW = 84, pillH = 20, gap = 6;
      var totalW = pills.length * pillW + (pills.length - 1) * gap;
      var startX = cx - totalW / 2;
      ctx.font = '600 11px Inter, system-ui, sans-serif';
      pills.forEach(function (p, i) {
        var px = startX + i * (pillW + gap);
        var py = pillY - pillH;
        // Pill background
        ctx.fillStyle = 'rgba(10, 14, 26, 0.7)';
        roundRect(ctx, px, py, pillW, pillH, 11);
        ctx.fill();
        ctx.strokeStyle = 'rgba(120, 145, 200, 0.25)';
        ctx.lineWidth = 1;
        ctx.stroke();
        // Status dot
        ctx.fillStyle = p.c;
        ctx.beginPath();
        ctx.arc(px + 12, py + pillH / 2, 3.5, 0, Math.PI * 2);
        ctx.fill();
        // Label
        ctx.fillStyle = 'rgba(242, 244, 248, 0.92)';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        ctx.fillText(p.label, px + 22, py + pillH / 2);
      });

      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
    return { dispose: function () { _rafStop = true; } };
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y,     x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x,     y + h, r);
    ctx.arcTo(x,     y + h, x,     y,     r);
    ctx.arcTo(x,     y,     x + w, y,     r);
    ctx.closePath();
  }

  function hexToRgba(hex, alpha) {
    var h = hex.replace('#', '');
    if (h.length === 3) h = h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
    var r = parseInt(h.substring(0, 2), 16);
    var g = parseInt(h.substring(2, 4), 16);
    var b = parseInt(h.substring(4, 6), 16);
    return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
  }

  // ---------------------------------------------------------------------------
  // Public mount. Single Canvas-only path.
  // ---------------------------------------------------------------------------
  function mount(selector, options) {
    options = options || {};
    var host = typeof selector === 'string' ? document.querySelector(selector) : selector;
    if (!host) return null;
    var hotspots = options.hotspots || DEFAULT_HOTSPOTS;
    return _renderCanvas(host, hotspots);
  }

  // Expose on MS namespace and as window.MS.globe for direct use.
  function _attachToMS() {
    window.MS = window.MS || {};
    window.MS.globe = { mount: mount, DEFAULT_HOTSPOTS: DEFAULT_HOTSPOTS };
  }
  _attachToMS();

  // Auto-mount any .ms-globe element on DOMContentLoaded.
  document.addEventListener('DOMContentLoaded', function () {
    var hosts = document.querySelectorAll('.ms-globe');
    hosts.forEach(function (h) { mount(h); });
  });
})();