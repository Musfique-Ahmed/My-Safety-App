/* ============================================================================
 * globe.js — WebGL Dhaka hero (with Canvas + static-SVG fallback).
 *
 * Renders into <div class="ms-globe" id="ms-globe"></div>. The page must
 * include a call to MS.globe.mount('#ms-globe') (or rely on auto-mount when
 * the element is present on DOMContentLoaded).
 *
 * Visual: a luminous, dark globe centred on Dhaka (≈23.81°N, 90.41°E), with
 * alert points pulsing on known hotspots. Camera can be dragged to orbit
 * (mouse + touch). Auto-rotation is on by default; the spin stops on
 * prefers-reduced-motion.
 *
 * Stack: three.js (CDN, ESM via importmap) + three-globe. If WebGL is
 * unavailable (older browser, blocked GPU), we fall back to a Canvas-painted
 * concentric radar anchored on Dhaka. The radial pulse and callouts stay.
 * ============================================================================ */

(function () {
  'use strict';

  // Default alert hot-spots (area-name, lat, lng, severity, label)
  var DEFAULT_HOTSPOTS = [
    { lat: 23.7949, lng: 90.4137, sev: 'red',   label: 'Gulshan' },
    { lat: 23.7462, lng: 90.3776, sev: 'amber', label: 'Dhanmondi' },
    { lat: 23.8759, lng: 90.3979, sev: 'green', label: 'Uttara' },
    { lat: 23.7275, lng: 90.4109, sev: 'amber', label: 'Motijheel' },
    { lat: 23.7383, lng: 90.4005, sev: 'blue',  label: 'Ramna' },
    { lat: 23.7845, lng: 90.4124, sev: 'red',   label: 'Badda' },
    { lat: 23.8062, lng: 90.3601, sev: 'blue',  label: 'Mirpur' },
    { lat: 23.7608, lng: 90.3580, sev: 'green', label: 'Mohammadpur' }
  ];

  // Dhaka — our home.
  var DHAKA_LAT = 23.8103;
  var DHAKA_LNG = 90.4125;

  var REDUCED_MOTION = (typeof window !== 'undefined' && window.matchMedia)
    ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
    : false;

  function _hasWebGL() {
    try {
      var c = document.createElement('canvas');
      return !!(c.getContext('webgl2') || c.getContext('webgl') || c.getContext('experimental-webgl'));
    } catch (e) { return false; }
  }

  function _isOnline() { return navigator.onLine !== false; }

  // ---------------------------------------------------------------------------
  // Canvas fallback — a Dhaka-anchored radar with pulsing rings. Keeps the
  // dashboard looking alive even when WebGL is unavailable.
  // ---------------------------------------------------------------------------
  function _renderCanvasFallback(host, hotspots) {
    host.innerHTML = '';
    var size = Math.min(host.clientWidth || 560, host.clientHeight || 560);
    if (!size) size = 560;
    var canvas = document.createElement('canvas');
    canvas.width = size * 2;
    canvas.height = size * 2;
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    host.appendChild(canvas);
    var ctx = canvas.getContext('2d');
    var cx = canvas.width / 2;
    var cy = canvas.height / 2;
    var maxR = canvas.width * 0.46;
    var t0 = performance.now();

    function sevColor(sev) {
      return ({
        red:   '#EF4E5A',
        amber: '#F2A93B',
        green: '#3BCB8A',
        blue:  '#5B7CFA'
      })[sev] || '#5B7CFA';
    }

    function frame(now) {
      var t = (now - t0) / 1000;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Solid globe disc — the dark blue that the WebGL globe would render.
      var discGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, maxR);
      discGrad.addColorStop(0,    'rgba(36, 56, 96, 0.95)');
      discGrad.addColorStop(0.6,  'rgba(20, 28, 48, 0.92)');
      discGrad.addColorStop(1,    'rgba(10, 14, 26, 0.85)');
      ctx.fillStyle = discGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, maxR, 0, Math.PI * 2);
      ctx.fill();

      // Concentric "radar" rings
      ctx.lineWidth = 1;
      for (var i = 1; i <= 4; i++) {
        ctx.strokeStyle = 'rgba(124,155,255,' + (0.18 - i * 0.03) + ')';
        ctx.beginPath();
        ctx.arc(cx, cy, (maxR * i) / 4, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Crosshair
      ctx.strokeStyle = 'rgba(124,155,255,0.10)';
      ctx.beginPath();
      ctx.moveTo(cx - maxR, cy); ctx.lineTo(cx + maxR, cy);
      ctx.moveTo(cx, cy - maxR); ctx.lineTo(cx, cy + maxR);
      ctx.stroke();

      // Hub: Dhaka
      var pulse = 0.5 + 0.5 * Math.sin(t * 1.6);
      var hubR = 18 + pulse * 4;
      var grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, hubR * 4);
      grad.addColorStop(0,   'rgba(124,155,255,0.55)');
      grad.addColorStop(0.4, 'rgba(124,155,255,0.18)');
      grad.addColorStop(1,   'rgba(124,155,255,0)');
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, cy, hubR * 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#7C9BFF';
      ctx.beginPath();
      ctx.arc(cx, cy, hubR, 0, Math.PI * 2);
      ctx.fill();

      // Spokes for headings
      ctx.strokeStyle = 'rgba(166,176,197,0.25)';
      ctx.lineWidth = 1;
      for (var a = 0; a < 360; a += 45) {
        var rad = a * Math.PI / 180;
        var x1 = cx + Math.cos(rad) * (hubR + 6);
        var y1 = cy + Math.sin(rad) * (hubR + 6);
        var x2 = cx + Math.cos(rad) * maxR;
        var y2 = cy + Math.sin(rad) * maxR;
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
      }

      // Hot-spots as small luminous points distributed around Dhaka. The
      // spread is purely visual; the data is what matters.
      hotspots.forEach(function (h, i) {
        var ang = (i / hotspots.length) * Math.PI * 2 + t * 0.05;
        var dist = maxR * (0.45 + 0.25 * Math.abs(Math.sin(i + t * 0.3)));
        var x = cx + Math.cos(ang) * dist;
        var y = cy + Math.sin(ang) * dist;
        var r = 6 + 3 * Math.sin(t * 2 + i);
        var g2 = ctx.createRadialGradient(x, y, 0, x, y, r * 4);
        g2.addColorStop(0, sevColor(h.sev));
        g2.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = g2;
        ctx.beginPath(); ctx.arc(x, y, r * 4, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = sevColor(h.sev);
        ctx.beginPath(); ctx.arc(x, y, r * 0.6, 0, Math.PI * 2); ctx.fill();
      });

      // Center label
      ctx.fillStyle = 'rgba(242,244,248,0.85)';
      ctx.font = '600 26px Inter, system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('DHAKA', cx, cy - maxR - 14);
      ctx.fillStyle = 'rgba(166,176,197,0.75)';
      ctx.font = '500 12px JetBrains Mono, monospace';
      ctx.fillText('23.81° N  ·  90.41° E', cx, cy - maxR - 30);

      if (!_rafStop) requestAnimationFrame(frame);
    }
    var _rafStop = false;
    requestAnimationFrame(frame);
    return { dispose: function () { _rafStop = true; } };
  }


  // ---------------------------------------------------------------------------
  // WebGL path — three.js + three-globe via CDN (importmap).
  // ---------------------------------------------------------------------------
  function _renderWebGL(host, hotspots) {
    host.innerHTML = '';
    return new Promise(function (resolve) {
      function _build(THREE, ThreeGlobe) {
        if (!THREE || !ThreeGlobe) {
          _renderCanvasFallback(host, hotspots);
          return resolve(null);
        }
        var w = host.clientWidth || 560;
        var h = host.clientHeight || 560;
        var scene = new THREE.Scene();
        scene.background = null;
        var camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 1000);
        camera.position.set(0, 0, 320);
        var renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setPixelRatio(window.devicePixelRatio || 1);
        renderer.setSize(w, h);
        host.appendChild(renderer.domElement);

        var glow = new THREE.Mesh(
          new THREE.SphereGeometry(100, 32, 32),
          new THREE.MeshBasicMaterial({ color: 0x10182e, transparent: true, opacity: 0.95 })
        );
        scene.add(glow);

        // Atmosphere ring (subtle outer glow)
        var atmosMat = new THREE.MeshBasicMaterial({
          color: 0x7C9BFF,
          transparent: true,
          opacity: 0.08,
          side: THREE.BackSide
        });
        var atmos = new THREE.Mesh(new THREE.SphereGeometry(110, 32, 32), atmosMat);
        scene.add(atmos);

        var Globe = new ThreeGlobe()
          .showAtmosphere(true)
          .atmosphereColor('#7C9BFF')
          .atmosphereAltitude(0.18)
          .hexPolygonsData([])
          .hexPolygonResolution(3)
          .hexPolygonMargin(0.4)
          .hexPolygonColor(function () { return 'rgba(124,155,255,0.35)'; })
          .showGlobe(true)
          .globeMaterial(new THREE.MeshPhongMaterial({
            color: 0x2a3a64,
            emissive: 0x162038,
            emissiveIntensity: 0.6,
            shininess: 8
          }));

        // Lights
        var ambient = new THREE.AmbientLight(0x6b7794, 0.8);
        scene.add(ambient);
        var key = new THREE.DirectionalLight(0xffffff, 0.6);
        key.position.set(200, 200, 200);
        scene.add(key);
        var rim = new THREE.DirectionalLight(0x7C9BFF, 0.4);
        rim.position.set(-200, -100, 100);
        scene.add(rim);

        scene.add(Globe);

        // PointsData
        var pointData = hotspots.map(function (h) {
          return { lat: h.lat, lng: h.lng, color: _sevHex(h.sev), label: h.label };
        });
        Globe
          .htmlElementsData(pointData)
          .htmlElement(function (d) {
            var el = document.createElement('div');
            el.className = 'ms-globe__pt ms-globe__pt--' + d.color;
            el.title = d.label;
            el.setAttribute('data-label', d.label);
            return el;
          })
          .htmlAltitude(function () { return 0.6; });

        // Camera pivot for orbit
        var pivot = new THREE.Object3D();
        scene.add(pivot);
        pivot.add(Globe);

        // Centre on Dhaka
        var lat = DHAKA_LAT * Math.PI / 180;
        var lng = DHAKA_LNG * Math.PI / 180;
        Globe.rotation.y = -lng + Math.PI; // approximate: rotate globe so Dhaka faces camera
        Globe.rotation.x = lat - Math.PI / 2;

        // Drag-to-orbit
        var dragging = false;
        var lastX = 0, lastY = 0;
        renderer.domElement.addEventListener('pointerdown', function (e) {
          dragging = true; lastX = e.clientX; lastY = e.clientY;
          renderer.domElement.setPointerCapture(e.pointerId);
        });
        renderer.domElement.addEventListener('pointerup', function (e) {
          dragging = false; try { renderer.domElement.releasePointerCapture(e.pointerId); } catch (_) {}
        });
        renderer.domElement.addEventListener('pointermove', function (e) {
          if (!dragging) return;
          var dx = e.clientX - lastX;
          var dy = e.clientY - lastY;
          pivot.rotation.y += dx * 0.005;
          pivot.rotation.x = Math.max(-1.2, Math.min(1.2, pivot.rotation.x + dy * 0.005));
          lastX = e.clientX; lastY = e.clientY;
        });

        // Resize
        function onResize() {
          var nw = host.clientWidth || 560;
          var nh = host.clientHeight || 560;
          renderer.setSize(nw, nh);
          camera.aspect = nw / nh;
          camera.updateProjectionMatrix();
        }
        window.addEventListener('resize', onResize);

        var t0 = performance.now();
        var _raf = true;
        function frame(now) {
          if (!_raf) return;
          if (!REDUCED_MOTION && !dragging) {
            pivot.rotation.y += 0.0009;
          }
          // Subtle pulse on point elements via CSS — done in CSS, nothing here.
          renderer.render(scene, camera);
          requestAnimationFrame(frame);
        }
        requestAnimationFrame(frame);

        resolve({
          dispose: function () {
            _raf = false;
            window.removeEventListener('resize', onResize);
            renderer.dispose();
            host.innerHTML = '';
          }
        });
      }

      function _sevHex(sev) {
        return ({ red: 'red', amber: 'amber', green: 'green', blue: 'blue' })[sev] || 'blue';
      }

      // Lazy-inject three.js + three-globe via plain <script> tags. We use the
      // IIFE bundle of three-globe (no importmap / no ESM resolution chain
      // needed) and a non-module three.js build so THREE lands on `window`.
      function _loadScript(src) {
        return new Promise(function (res, rej) {
          var s = document.createElement('script');
          s.src = src; s.async = true;
          s.onload = function () { res(); };
          s.onerror = function () { rej(new Error('failed to load ' + src)); };
          document.head.appendChild(s);
        });
      }

      var handled = false;
      function onReady() {
        if (handled) return; handled = true;
        _build(window.THREE, window.ThreeGlobe);
      }

      _loadScript('https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js')
        .then(function () {
          return _loadScript('https://cdn.jsdelivr.net/npm/three-globe@2.31.1/dist/three-globe.min.js');
        })
        .then(function () {
          // Both loaded — small delay to let the UMD wrapper finish attaching.
          setTimeout(onReady, 0);
        })
        .catch(function (err) {
          if (handled) return;
          handled = true;
          console.warn('[ms-globe] failed to load WebGL bundle, falling back to canvas radar.', err);
          _renderCanvasFallback(host, hotspots);
          resolve(null);
        });

      // Fallback timer — if WebGL hasn't booted in 8s, drop to Canvas.
      setTimeout(function () {
        if (!handled) {
          handled = true;
          _renderCanvasFallback(host, hotspots);
          resolve(null);
        }
      }, 8000);
    });
  }


  // ---------------------------------------------------------------------------
  // Public mount
  // ---------------------------------------------------------------------------
  function mount(selector, options) {
    options = options || {};
    var host = typeof selector === 'string' ? document.querySelector(selector) : selector;
    if (!host) return null;
    var hotspots = options.hotspots || DEFAULT_HOTSPOTS;

    if (_hasWebGL() && _isOnline()) {
      return _renderWebGL(host, hotspots);
    }
    return _renderCanvasFallback(host, hotspots);
  }

  // Expose on MS namespace (set by console.js) and as window.MS.globe for
  // direct use.
  function _attachToMS() {
    if (window.MS) {
      window.MS.globe = { mount: mount, DEFAULT_HOTSPOTS: DEFAULT_HOTSPOTS };
    } else {
      // console.js not yet on the page — install a shim.
      window.MS = window.MS || {};
      window.MS.globe = { mount: mount, DEFAULT_HOTSPOTS: DEFAULT_HOTSPOTS };
    }
  }
  _attachToMS();

  // Auto-mount any .ms-globe element on DOMContentLoaded.
  document.addEventListener('DOMContentLoaded', function () {
    var hosts = document.querySelectorAll('.ms-globe');
    hosts.forEach(function (h) { mount(h); });
  });
})();