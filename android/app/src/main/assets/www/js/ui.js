/* Small UI toolkit: element builder, icons, sheets, toasts, confirm, colour picker, date field. */
(function (root) {
  'use strict';
  var t = function (k, v) { return I18n.t(k, v); };

  function h(tag, attrs) {
    var el = document.createElement(tag), kids = Array.prototype.slice.call(arguments, 2);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v === undefined || v === null || v === false) return;
      if (k === 'class') el.className = v;
      else if (k === 'style' && typeof v === 'object') Object.keys(v).forEach(function (p) { p.indexOf('--') === 0 ? el.style.setProperty(p, v[p]) : (el.style[p] = v[p]); });
      else if (k === 'html') el.innerHTML = v;
      else if (k.slice(0, 2) === 'on' && typeof v === 'function') el.addEventListener(k.slice(2), v);
      else if (v === true) el.setAttribute(k, '');
      else el.setAttribute(k, v);
    });
    (function add(list) { list.forEach(function (c) { if (Array.isArray(c)) return add(c); if (c === null || c === undefined || c === false) return; el.appendChild(c.nodeType ? c : document.createTextNode(String(c))); }); })(kids);
    return el;
  }
  var P = {
    today: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    stats: '<path d="M4 20V10M10 20V4M16 20v-8M22 20H2"/>',
    exams: '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h7M9 17h5"/>',
    tasks: '<rect x="4" y="4" width="16" height="16" rx="4"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
    more: '<circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/>',
    play: '<path d="M7 4.5v15l13-7.5z"/>', stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    plus: '<path d="M12 5v14M5 12h14"/>', trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6"/>',
    edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13 7 4 4"/>', check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    sync: '<path d="M20 11a8 8 0 0 0-14-4M4 5v4h4M4 13a8 8 0 0 0 14 4M20 19v-4h-4"/>', wifi: '<path d="M2 9a15 15 0 0 1 20 0M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0"/><circle cx="12" cy="19" r="1"/>',
    file: '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5"/>', share: '<path d="M12 16V4M7 9l5-5 5 5M5 14v6h14v-6"/>',
    down: '<path d="M12 4v12M7 11l5 5 5-5M5 20h14"/>', up: '<path d="M12 20V8M7 13l5-5 5 5M5 4h14"/>', globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1"/>', book: '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zM4 19V5"/>',
    close: '<path d="M6 6l12 12M18 6 6 18"/>', info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>'
  };
  function icon(name) { return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">' + (P[name] || '') + '</svg>'; }
  function ic(name, cls) { return h('span', { class: cls || '', html: icon(name), style: { display: 'inline-flex' } }); }

  // ---------------------------------------------------------------- toasts
  function toast(msg, kind) {
    var box = document.getElementById('toasts'), el = h('div', { class: 'toast ' + (kind || '') }, msg);
    box.appendChild(el); setTimeout(function () { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; setTimeout(function () { el.remove(); }, 320); }, 2600);
  }

  // ---------------------------------------------------------------- sheets (bottom panels)
  var stack = [];
  function sheet(opts) {
    var layer = document.getElementById('layer'), scrim = h('div', { class: 'scrim' }), body = h('div', { class: 'sheet-body' }, opts.body);
    var actions = opts.actions ? h('div', { class: 'actions' }, opts.actions) : null;
    var el = h('div', { class: 'sheet', role: 'dialog' }, h('div', { class: 'grab' }), opts.title ? h('h2', null, opts.title) : null,
      opts.message ? h('div', { class: 'muted small', style: { marginBottom: '6px' } }, opts.message) : null, body, actions);
    var api = { el: el, body: body, closed: false, close: function (result) {
      if (api.closed) return; api.closed = true; scrim.classList.remove('on'); el.classList.remove('on');
      stack = stack.filter(function (s) { return s !== api; });
      setTimeout(function () { scrim.remove(); el.remove(); if (!stack.length) layer.style.pointerEvents = 'none'; }, 260);
      if (opts.onClose) opts.onClose(result);
    } };
    scrim.addEventListener('click', function () { api.close(null); });
    layer.style.pointerEvents = 'auto'; layer.appendChild(scrim); layer.appendChild(el); stack.push(api);
    requestAnimationFrame(function () { scrim.classList.add('on'); el.classList.add('on'); });
    return api;
  }
  function closeTop() { var s = stack[stack.length - 1]; if (s) { s.close(null); return true; } return false; }
  function confirmSheet(title, message, okText, danger) {
    return new Promise(function (resolve) {
      var done = false, s;
      function fin(v) { if (!done) { done = true; resolve(v); } s.close(v); }
      s = sheet({ title: title, message: message, body: null, onClose: function () { if (!done) { done = true; resolve(false); } },
        actions: [h('button', { class: 'btn', onclick: function () { fin(false); } }, t('cancel')),
                  h('button', { class: 'btn ' + (danger ? 'danger' : 'primary'), onclick: function () { fin(true); } }, okText || t('confirm'))] });
    });
  }

  // ---------------------------------------------------------------- colour picker (wheel button + HSV panel)
  function hsv2hex(hh, s, v) {
    var f = function (n) { var k = (n + hh * 6) % 6; return v - v * s * Math.max(0, Math.min(k, 4 - k, 1)); };
    function x(a) { return ('0' + Math.round(a * 255).toString(16)).slice(-2).toUpperCase(); }
    return '#' + x(f(5)) + x(f(3)) + x(f(1));
  }
  function hex2hsv(hex) {
    var r = parseInt(hex.slice(1, 3), 16) / 255, g = parseInt(hex.slice(3, 5), 16) / 255, b = parseInt(hex.slice(5, 7), 16) / 255;
    var mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn, hh = 0;
    if (d) { if (mx === r) hh = ((g - b) / d + (g < b ? 6 : 0)) / 6; else if (mx === g) hh = ((b - r) / d + 2) / 6; else hh = ((r - g) / d + 4) / 6; }
    return { h: hh, s: mx ? d / mx : 0, v: mx };
  }
  function pickColor(start) {
    return new Promise(function (resolve) {
      var c = hex2hsv(Core.normalizeColor(start) || '#8B5CF6'); if (c.s < 0.001) c.h = 0.7;
      var sv = h('div', { class: 'sv' }), svBg = h('div', { class: 'layer' }), svW = h('div', { class: 'layer', style: { background: 'linear-gradient(90deg,#fff,rgba(255,255,255,0))' } }),
          svB = h('div', { class: 'layer', style: { background: 'linear-gradient(0deg,#000,rgba(0,0,0,0))' } }), svK = h('div', { class: 'knob' });
      sv.append(svBg, svW, svB, svK);
      var hue = h('div', { class: 'hue' }), hk = h('div', { class: 'knob' }); hue.append(hk);
      var prev = h('div', { class: 'preview' }), hex = h('input', { type: 'text', class: 'hex', maxlength: 7, placeholder: '#RRGGBB', autocapitalize: 'characters', spellcheck: 'false' }),
          hint = h('div', { class: 'small dim', style: { marginTop: '8px' } }, t('colour_lifted'));
      function raw() { return hsv2hex(c.h >= 1 ? 0.999 : c.h, c.s, c.v); }
      function fin() { return Core.normalizeColor(raw()) || raw(); }
      function paint(setHex) {
        svBg.style.background = hsv2hex(c.h >= 1 ? 0.999 : c.h, 1, 1);
        svK.style.left = (c.s * 100) + '%'; svK.style.top = ((1 - c.v) * 100) + '%'; svK.style.background = raw();
        hk.style.left = (c.h * 100) + '%'; hk.style.background = hsv2hex(c.h, 1, 1);
        prev.style.background = fin(); hint.style.display = fin() !== raw() ? 'block' : 'none';
        if (setHex !== false) hex.value = raw();
      }
      function drag(el, fn) {
        function mv(e) { var r = el.getBoundingClientRect(); fn(Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), Math.min(1, Math.max(0, (e.clientY - r.top) / r.height))); paint(); }
        el.addEventListener('pointerdown', function (e) { el.setPointerCapture(e.pointerId); mv(e); el.onpointermove = mv; });
        el.addEventListener('pointerup', function () { el.onpointermove = null; });
      }
      drag(sv, function (x, y) { c.s = x; c.v = 1 - y; });
      drag(hue, function (x) { c.h = x; });
      hex.addEventListener('input', function () {
        var v = hex.value.trim().replace(/^#/, ''); if (v.length === 3) v = v.split('').map(function (ch) { return ch + ch; }).join('');
        if (/^[0-9a-fA-F]{6}$/.test(v)) { var n = hex2hsv('#' + v); if (n.s > 0.001 && n.v > 0.001) c.h = n.h; c.s = n.s; c.v = n.v; paint(false); }
      });
      var s = sheet({ title: t('choose_colour'), body: [sv, hue, h('div', { class: 'row', style: { marginTop: '10px' } }, prev, hex), hint],
        onClose: function (r) { resolve(r || null); },
        actions: [h('button', { class: 'btn', onclick: function () { s.close(null); } }, t('cancel')), h('button', { class: 'btn primary', onclick: function () { s.close(fin()); } }, t('select'))] });
      paint();
    });
  }
  /* returns {el, get(), set(hex)} */
  function colorField(initial, onChange) {
    var cur = initial || Core.SUBJECT_COLORS[0], custom = null, wrap = h('div', { class: 'swatches' });
    var presets = Core.SUBJECT_COLORS;
    if (presets.indexOf(cur) < 0) custom = cur;
    function draw() {
      wrap.innerHTML = '';
      presets.forEach(function (c) { wrap.appendChild(h('button', { type: 'button', class: 'sw' + (cur === c ? ' on' : ''), style: { '--c': c }, 'aria-label': c, onclick: function () { cur = c; draw(); onChange && onChange(cur); } })); });
      if (custom) wrap.appendChild(h('button', { type: 'button', class: 'sw' + (cur === custom ? ' on' : ''), style: { '--c': custom }, onclick: function () { cur = custom; draw(); onChange && onChange(cur); } }));
      wrap.appendChild(h('button', { type: 'button', class: 'sw wheel', title: t('custom_color'), onclick: function () {
        pickColor(cur).then(function (c) { if (!c) return; if (presets.indexOf(c) >= 0) cur = c; else { custom = c; cur = c; } draw(); onChange && onChange(cur); });
      } }, h('i', null, '+')));
    }
    draw();
    return { el: wrap, get: function () { return cur; }, set: function (c) { cur = c; if (presets.indexOf(c) < 0) custom = c; draw(); } };
  }

  // ---------------------------------------------------------------- date field: Jalali selects (fa) or a native date input (en)
  function dateField(value, onChange) {
    var cur = value || Core.dkey();
    if (I18n.lang !== 'fa') {
      var inp = h('input', { type: 'date', value: cur, onchange: function () { if (inp.value) { cur = inp.value; onChange && onChange(cur); } } });
      return { el: inp, get: function () { return inp.value || cur; }, set: function (v) { cur = v; inp.value = v; } };
    }
    var d = Core.parseDkey(cur), j = Jalali.toJalali(d.getFullYear(), d.getMonth() + 1, d.getDate());
    var sy = h('select'), sm = h('select'), sd = h('select');
    var months = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
    var nowJ = Jalali.toJalali(new Date().getFullYear(), new Date().getMonth() + 1, new Date().getDate());
    for (var y = Math.min(nowJ.jy - 3, j.jy); y <= Math.max(nowJ.jy + 3, j.jy); y++) sy.appendChild(h('option', { value: y }, I18n.digits(y)));
    months.forEach(function (m, i) { sm.appendChild(h('option', { value: i + 1 }, m)); });
    function days() {
      var n = Jalali.monthLength(+sy.value, +sm.value), keep = +sd.value || j.jd; sd.innerHTML = '';
      for (var i = 1; i <= n; i++) sd.appendChild(h('option', { value: i }, I18n.digits(i)));
      sd.value = Math.min(keep, n);
    }
    sy.value = j.jy; sm.value = j.jm; days(); sd.value = j.jd;
    function get() { var g = Jalali.toGregorian(+sy.value, +sm.value, +sd.value); return g.gy + '-' + ('0' + g.gm).slice(-2) + '-' + ('0' + g.gd).slice(-2); }
    sy.onchange = sm.onchange = function () { days(); onChange && onChange(get()); }; sd.onchange = function () { onChange && onChange(get()); };
    var el = h('div', { class: 'row' }, h('div', { class: 'grow' }, sd), h('div', { class: 'grow', style: { flex: '1.6' } }, sm), h('div', { class: 'grow', style: { flex: '1.2' } }, sy));
    return { el: el, get: get, set: function (v) { var dd = Core.parseDkey(v), jj = Jalali.toJalali(dd.getFullYear(), dd.getMonth() + 1, dd.getDate()); sy.value = jj.jy; sm.value = jj.jm; days(); sd.value = jj.jd; } };
  }
  function field(label, control) { return [h('label', { class: 'field' }, label), control]; }

  var UI = { h: h, icon: icon, ic: ic, toast: toast, sheet: sheet, closeTop: closeTop, confirm: confirmSheet, pickColor: pickColor, colorField: colorField, dateField: dateField, field: field, hsv2hex: hsv2hex, hex2hsv: hex2hsv };
  root.UI = UI;
})(typeof window !== 'undefined' ? window : globalThis);
