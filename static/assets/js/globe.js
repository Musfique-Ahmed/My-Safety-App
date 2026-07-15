/* ============================================================================
 * globe.js — Bangladesh operations radar.
 *
 * Renders into <div class="ms-globe" id="ms-globe"></div>. The page must
 * include a call to MS.globe.mount('#ms-globe') (or rely on auto-mount when
 * the element is present on DOMContentLoaded).
 *
 * Visual: a luminous dark radar disc covering all of Bangladesh. On top of
 * the disc we draw:
 *   - The Bangladesh landmass (stylised but recognisable outline)
 *   - Major rivers (Padma / Meghna / Jamuna / Brahmaputra)
 *   - District hot-spot markers across the country in status colours
 *   - The DHAKA capital hub (brightest point)
 *   - A slow rotating sweep arm (radar-style)
 *   - "BANGLADESH · NATIONAL OPERATIONS RADAR" rim caption
 *
 * The radar is centred on the country's geographic centroid (~23.65°N,
 * 90.35°E) — close to Dhaka but a touch west so the whole country fits
 * symmetrically inside the disc. DHAKA is still drawn as the brightest hub
 * on top of the map (the capital, the operational heart).
 *
 * Pure 2D Canvas implementation — no WebGL, no three.js. Works on integrated
 * graphics, headless Chromium, and offline. Reduced-motion users get a
 * static map.
 * ============================================================================ */

(function () {
  'use strict';

  // Geographic anchors.
  // Centroid of Bangladesh — derived from the polygon's bounding box
  // (lng 87.95..92.30 → 90.125, lat 21.25..26.45 → 23.85). Setting the
  // projection centre to the polygon centroid means the country fills
  // the disc symmetrically.
  var CENTROID_LAT = 23.85;
  var CENTROID_LNG = 90.13;

  // The Dhaka capital — drawn as the brightest hub on top of the map.
  // Slightly south-east of the geometric centroid so the country looks
  // centred while Dhaka sits where it actually is.
  var DHAKA_LAT = 23.8103;
  var DHAKA_LNG = 90.4125;

  // The canvas extent we map onto: tight fit to the actual country outline
  // with a small visual margin. Bangladesh spans roughly 4.35° lng ×
  // 5.20° lat. We size the projection so the country fills most of the
  // disc (not floats in the middle of an oversized buffer).
  var LNG_SPAN = 5.4;
  var LAT_SPAN = 6.5;

  // Default alert hot-spots. Real coordinates of major cities / district
  // seats across all of Bangladesh, so the radar shows nationwide activity
  // rather than just Dhaka. Severity drives colour only.
  var DEFAULT_HOTSPOTS = [
    // Dhaka Division
    { lat: 23.8103, lng: 90.4125, sev: 'red',   label: 'Dhaka' },
    { lat: 23.7462, lng: 90.3776, sev: 'amber', label: 'Dhanmondi' },
    { lat: 23.7275, lng: 90.4109, sev: 'amber', label: 'Motijheel' },
    { lat: 23.8759, lng: 90.3979, sev: 'green', label: 'Uttara' },
    { lat: 23.7845, lng: 90.4124, sev: 'red',   label: 'Badda' },
    // Chittagong Division
    { lat: 22.3569, lng: 91.7832, sev: 'red',   label: 'Chittagong' },
    { lat: 22.7010, lng: 90.3745, sev: 'amber', label: 'Barisal' },
    { lat: 22.8734, lng: 91.0974, sev: 'blue',  label: 'Noakhali' },
    // Sylhet Division
    { lat: 24.8949, lng: 91.8687, sev: 'amber', label: 'Sylhet' },
    { lat: 25.0730, lng: 91.3990, sev: 'blue',  label: 'Moulvibazar' },
    // Khulna Division
    { lat: 22.8456, lng: 89.5403, sev: 'green', label: 'Khulna' },
    { lat: 23.1634, lng: 89.2182, sev: 'blue',  label: 'Jessore' },
    // Rajshahi Division
    { lat: 24.3745, lng: 88.6042, sev: 'green', label: 'Rajshahi' },
    { lat: 24.7106, lng: 88.9564, sev: 'blue',  label: 'Nawabganj' },
    // Rangpur Division
    { lat: 25.7439, lng: 89.2752, sev: 'amber', label: 'Rangpur' },
    { lat: 25.6270, lng: 88.6364, sev: 'blue',  label: 'Dinajpur' },
    // Mymensingh Division
    { lat: 24.7471, lng: 90.4203, sev: 'green', label: 'Mymensingh' }
  ];

  // Stylised Bangladesh landmass. Hand-traced from the country's actual
  // fish-shape silhouette: narrow head in the north, central waist (Dhaka
  // division), wide Ganges delta bulging south across the Bay of Bengal
  // coast (Khulna / Barisal / Noakhali), the Sundarbans mangrove belt in
  // the south-west, the Sylhet lobe bulging east, and the long south-east
  // tail of Chittagong → Cox's Bazar. Coordinates are deliberately
  // smoothed — it's a brand element, not a navigation chart.
  // Each entry is [lng, lat]; lat/lng are mapped to canvas via the same
  // projection as the hot-spots below. Tracing order: clockwise from the
  // north-west corner.
  var LANDMASS = [
    // ─ North-west corner (Panchagarh / Thakurgaon)
    [88.55, 26.45],
    // ─ North edge running east (Dinajpur, Rangpur, Kurigram)
    [88.85, 26.30], [89.20, 26.10], [89.55, 25.95], [89.85, 25.85], [90.15, 25.75],
    // ─ North-east: Mymensingh / Netrokona dipping toward Sylhet basin
    [90.55, 25.60], [90.95, 25.45], [91.30, 25.30], [91.60, 25.10],
    // ─ Sylhet lobe (NE bulge — only ~50km east of the rest)
    [91.85, 24.95], [92.05, 24.85], [92.25, 24.95], [92.30, 25.15],
    [92.10, 25.25], [91.90, 25.20], [91.75, 25.10],
    // ─ East edge going south (Comilla, Feni, Chittagong outskirts)
    [91.85, 24.55], [91.95, 24.05], [92.00, 23.50], [91.95, 23.00],
    // ─ Chittagong port bulge
    [91.80, 22.65], [91.85, 22.35], [92.05, 22.10],
    // ─ Cox's Bazar / Teknaf — the long south-east tail
    [92.20, 21.75], [92.30, 21.45], [92.25, 21.25],
    // ─ South coast sweeping west (Noakhali, Barisal, Khulna — wide delta bulge)
    [91.80, 22.05], [91.40, 22.30], [91.00, 22.45], [90.60, 22.55], [90.20, 22.55],
    [89.85, 22.45], [89.50, 22.30], [89.20, 22.10],
    // ─ Sundarbans (south-west, gently dipping south)
    [88.95, 21.85], [88.75, 21.70], [88.55, 21.85], [88.40, 22.10],
    // ─ West edge going north (Jessore, Rajshahi side)
    [88.20, 22.50], [88.05, 23.00], [87.95, 23.55], [87.95, 24.10],
    [88.05, 24.65], [88.15, 25.15], [88.30, 25.65], [88.45, 26.10],
    // Close back to start
    [88.55, 26.45]
  ];

  // Stylised major rivers. Each entry is [lng, lat] along the river path.
  // These are drawn as thin hairlines for visual richness — not to scale.
  var RIVERS = [
    // Padma (main Ganges channel) — flows west to east across the south.
    [[88.85, 25.50], [89.10, 25.10], [89.50, 24.80], [89.85, 24.50], [90.20, 24.10], [90.55, 23.85]],
    // Jamuna (Brahmaputra) — flows north to south on the west-centre.
    [[89.50, 26.10], [89.70, 25.60], [89.80, 25.10], [89.85, 24.70], [89.85, 24.30]],
    // Meghna — joins Padma near the centre then flows south to the Bay.
    [[91.20, 25.10], [90.90, 24.70], [90.65, 24.30], [90.55, 23.85], [90.60, 23.30], [90.80, 22.80]],
    // Surma / Kushiyara (Sylhet basin).
    [[91.80, 25.00], [91.65, 24.80], [91.45, 24.60], [91.30, 24.50]]
  ];

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

  // Map lat/lng to (x, y) inside a disc of radius maxR centred on the
  // country centroid. lng/x scales by cos(lat) at the centroid so the
  // country keeps its proportions on the disc.
  function project(lat, lng, cx, cy, maxR) {
    var dLng = (lng - CENTROID_LNG) / LNG_SPAN;
    var dLat = (lat - CENTROID_LAT) / LAT_SPAN;
    var x = cx + dLng * maxR * Math.cos(CENTROID_LAT * Math.PI / 180);
    var y = cy - dLat * maxR;
    return { x: x, y: y };
  }

  // ---------------------------------------------------------------------------
  // Canvas radar — the default and only renderer. Bangladesh-wide, with the
  // country outline, rivers, district markers, status pulses, sweep, rim
  // label, and the bright DHAKA hub. Everything in one frame function.
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
    var maxR = size * 0.46;
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

      // ---- Compass ticks (subtle, only at the cardinal edges where they
      //      don't fight the rim caption or the status pills). We offset
      //      them inward so the N/E/S/W labels never sit on the rim.
      ctx.fillStyle = 'rgba(166, 176, 197, 0.40)';
      ctx.font = '600 9px JetBrains Mono, monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('W', cx - maxR + 12, cy);
      ctx.fillText('E', cx + maxR - 12, cy);
      ctx.fillText('S', cx, cy + maxR - 12);

      // ---- Bangladesh landmass silhouette ----
      // Filled first (so the sweep / hot-spots overlay on top), with a
      // bright outline so the country shape reads at a glance. We do an
      // outer glow pass before the inner fill to lift it off the disc.
      ctx.save();
      // Soft outer glow (drawn wider, semi-transparent).
      ctx.beginPath();
      var startedGlow = false;
      LANDMASS.forEach(function (pt) {
        var p = project(pt[1], pt[0], cx, cy, maxR);
        if (!startedGlow) { ctx.moveTo(p.x, p.y); startedGlow = true; }
        else { ctx.lineTo(p.x, p.y); }
      });
      ctx.closePath();
      ctx.strokeStyle = 'rgba(124, 200, 255, 0.35)';
      ctx.lineWidth = 6;
      ctx.lineJoin = 'round';
      ctx.stroke();
      ctx.restore();

      ctx.save();
      // Inner filled polygon.
      ctx.beginPath();
      var started = false;
      LANDMASS.forEach(function (pt) {
        var p = project(pt[1], pt[0], cx, cy, maxR);
        if (!started) { ctx.moveTo(p.x, p.y); started = true; }
        else { ctx.lineTo(p.x, p.y); }
      });
      ctx.closePath();
      var landGrad = ctx.createLinearGradient(cx, cy - maxR, cx, cy + maxR);
      landGrad.addColorStop(0,   'rgba(124, 155, 255, 0.30)');
      landGrad.addColorStop(1,   'rgba(91, 124, 250, 0.20)');
      ctx.fillStyle = landGrad;
      ctx.fill();
      // Bright outline on top.
      ctx.strokeStyle = 'rgba(180, 215, 255, 0.85)';
      ctx.lineWidth = 1.6;
      ctx.lineJoin = 'round';
      ctx.stroke();
      ctx.restore();

      // ---- Major rivers (stylised hairlines for visual richness) ----
      ctx.save();
      ctx.strokeStyle = 'rgba(124, 200, 255, 0.30)';
      ctx.lineWidth = 1.0;
      RIVERS.forEach(function (r) {
        ctx.beginPath();
        r.forEach(function (pt, i) {
          var p = project(pt[1], pt[0], cx, cy, maxR);
          if (i === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y);
        });
        ctx.stroke();
      });
      ctx.restore();

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

      // ---- District labels (small dots, drawn behind hot-spot pulses) ----
      ctx.font = '500 9px Inter, system-ui, sans-serif';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      hotspots.forEach(function (h) {
        var p = project(h.lat, h.lng, cx, cy, maxR);
        if (p.x < cx - maxR || p.x > cx + maxR || p.y < cy - maxR || p.y > cy + maxR) return;
        ctx.fillStyle = 'rgba(166, 176, 197, 0.55)';
        ctx.beginPath();
        ctx.arc(p.x, p.y, 1.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = 'rgba(166, 176, 197, 0.50)';
        ctx.fillText(h.label, p.x + 5, p.y - 6);
      });

      // ---- Hot-spot pulses (status-coloured) ----
      hotspots.forEach(function (h, i) {
        var p = project(h.lat, h.lng, cx, cy, maxR);
        if (p.x < cx - maxR || p.x > cx + maxR || p.y < cy - maxR || p.y > cy + maxR) return;
        var pulse = 0.5 + 0.5 * Math.sin(t * 1.8 + i * 0.7);
        var r = 6 + 3 * pulse;
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
        ctx.lineWidth = 1.0;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
        ctx.stroke();
      });

      // ---- DHAKA capital hub (the brightest point on the radar) ----
      var dhaka = project(DHAKA_LAT, DHAKA_LNG, cx, cy, maxR);
      var hubPulse = 0.5 + 0.5 * Math.sin(t * 1.6);
      var hubR = 18 + hubPulse * 7;
      var hubGrad = ctx.createRadialGradient(dhaka.x, dhaka.y, 0, dhaka.x, dhaka.y, hubR * 4);
      hubGrad.addColorStop(0,    'rgba(255, 255, 255, 0.50)');
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
      // Hub label (small, offset so it doesn't fight the central map labels)
      ctx.fillStyle = '#F2F4F8';
      ctx.font = '700 11px Inter, system-ui, sans-serif';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillText('DHAKA', dhaka.x + 10, dhaka.y - 12);
      ctx.fillStyle = 'rgba(166, 176, 197, 0.80)';
      ctx.font = '500 9px JetBrains Mono, monospace';
      ctx.fillText('23.81° N · 90.41° E', dhaka.x + 10, dhaka.y + 2);

      // ---- Rim caption (drawn inside the disc, near the top edge, so the
      // HTML-level .ms-globe__callout overlay (top-right) can't clip it).
      ctx.fillStyle = 'rgba(242, 244, 248, 0.92)';
      ctx.font = '700 14px Inter, system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('BANGLADESH', cx, cy - maxR + 24);
      ctx.fillStyle = 'rgba(166, 176, 197, 0.75)';
      ctx.font = '500 9px JetBrains Mono, monospace';
      ctx.fillText('NATIONAL OPERATIONS RADAR', cx, cy - maxR + 40);

      // ---- Status pills along the bottom rim ----
      // Centered horizontally inside the disc, kept high enough that the
      // pills never overlap the rim. Each pill is a tiny rounded chip.
      var counts = { red: 0, amber: 0, green: 0, blue: 0 };
      hotspots.forEach(function (h) { counts[h.sev] = (counts[h.sev] || 0) + 1; });
      var pills = [
        { c: '#EF4E5A', label: counts.red + ' active',   sev: 'red'   },
        { c: '#F2A93B', label: counts.amber + ' pending', sev: 'amber' },
        { c: '#3BCB8A', label: counts.green + ' cleared', sev: 'green' },
        { c: '#5B7CFA', label: counts.blue + ' info',     sev: 'blue'  }
      ];
      var pillW = 78, pillH = 22, gap = 8;
      var totalW = pills.length * pillW + (pills.length - 1) * gap;
      var startX = cx - totalW / 2;
      // Vertical centre: between the DHAKA hub label and the rim. The DHAKA
      // hub label sits just right of the hub, so push the pills below the
      // hub label and above the rim caption. cy + maxR * 0.55 lands them
      // cleanly inside the disc, equidistant from rim and hub.
      var pillY = cy + maxR * 0.62 - pillH / 2;
      ctx.font = '600 11px Inter, system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      pills.forEach(function (p, i) {
        var px = startX + i * (pillW + gap);
        var py = pillY;
        // Pill background — slightly translucent to read against the disc.
        ctx.fillStyle = 'rgba(8, 12, 24, 0.78)';
        roundRect(ctx, px, py, pillW, pillH, 11);
        ctx.fill();
        ctx.strokeStyle = hexToRgba(p.c, 0.45);
        ctx.lineWidth = 1;
        ctx.stroke();
        // Status dot
        ctx.fillStyle = p.c;
        ctx.beginPath();
        ctx.arc(px + 14, py + pillH / 2, 3.2, 0, Math.PI * 2);
        ctx.fill();
        // Label — colour matches the dot for instant semantic read.
        ctx.fillStyle = p.c;
        ctx.fillText(p.label, px + pillW / 2 + 8, py + pillH / 2);
      });
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';

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