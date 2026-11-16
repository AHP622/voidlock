/* Art: the art-directed components of the Deep Blue Cinematic design (css/cinema.css).
 *  - Art.hero:      the orbital focus timer (goal ring, 60 ticks that light up during a session, orbiting seconds dot, rotating light sweep)
 *  - Art.empty:     illustrated empty states
 *  - Art.countdown: glowing countdown ring (exams)
 * Nothing here owns data: the elapsed time always comes from Core.elapsed (saved start time), so a render, a tab switch or a
 * backgrounded app can never change what the timer shows. Per-second updates only touch text, a few attributes and transforms. */
(function (root) {
  'use strict';
  var h = UI.h, t = function (k, v) { return I18n.t(k, v); };
  var NS = 'http://www.w3.org/2000/svg';
  var S = 300, C = 150, R = 112, CIRC = 2 * Math.PI * R, lastFrac = 0;

  var WORDS = {
    fa: { m: 'صبح بخیر', a: 'ظهر بخیر', e: 'عصر بخیر', n: 'شب بخیر', idle: 'آماده‌ی تمرکز؟', run: 'در تمرکز عمیق', done: 'هدف امروز کامل شد' },
    en: { m: 'Good morning', a: 'Good afternoon', e: 'Good evening', n: 'Good night', idle: 'Ready to focus?', run: 'In deep focus', done: 'Daily goal reached' }
  };
  function words() { return WORDS[I18n.lang === 'fa' ? 'fa' : 'en']; }
  function greeting() { var hr = new Date().getHours(), w = words(); return hr < 5 ? w.n : hr < 12 ? w.m : hr < 17 ? w.a : hr < 21 ? w.e : w.n; }

  function ticksSvg() {
    var s = '';
    for (var i = 0; i < 60; i++) {
      var a = (i * 6 - 90) * Math.PI / 180, long = i % 5 === 0, r1 = long ? 126 : 130, r2 = 136;
      s += '<line class="tk' + (long ? ' lg' : '') + '" x1="' + (C + r1 * Math.cos(a)).toFixed(2) + '" y1="' + (C + r1 * Math.sin(a)).toFixed(2) + '" x2="' + (C + r2 * Math.cos(a)).toFixed(2) + '" y2="' + (C + r2 * Math.sin(a)).toFixed(2) + '"/>';
    }
    return s;
  }
  function orbitSvg() {
    return '<svg viewBox="0 0 ' + S + ' ' + S + '" aria-hidden="true"><defs>' +
      '<linearGradient id="hgA" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#67E8F9"/><stop offset=".5" stop-color="#00D9F5"/><stop offset="1" stop-color="#1769FF"/></linearGradient>' +
      '<radialGradient id="hgG"><stop offset="0" stop-color="#fff"/><stop offset=".35" stop-color="#67E8F9"/><stop offset="1" stop-color="#00D9F5" stop-opacity="0"/></radialGradient></defs>' +
      '<circle cx="' + C + '" cy="' + C + '" r="143" fill="none" class="rim"/>' +
      '<g class="ticks">' + ticksSvg() + '</g>' +
      '<circle cx="' + C + '" cy="' + C + '" r="' + R + '" fill="none" class="track" stroke-width="13"/>' +
      '<circle cx="' + C + '" cy="' + C + '" r="' + R + '" fill="none" class="arc-glow" stroke="url(#hgA)" stroke-width="13" stroke-linecap="round" stroke-dasharray="' + CIRC.toFixed(1) + '" stroke-dashoffset="' + CIRC.toFixed(1) + '" transform="rotate(-90 ' + C + ' ' + C + ')"/>' +
      '<circle cx="' + C + '" cy="' + C + '" r="' + R + '" fill="none" class="arc" stroke="url(#hgA)" stroke-width="11" stroke-linecap="round" stroke-dasharray="' + CIRC.toFixed(1) + '" stroke-dashoffset="' + CIRC.toFixed(1) + '" transform="rotate(-90 ' + C + ' ' + C + ')"/>' +
      '<g class="cap"><circle cx="' + C + '" cy="' + (C - R) + '" r="13" fill="url(#hgG)"/><circle cx="' + C + '" cy="' + (C - R) + '" r="4.5" fill="#fff"/></g>' +
      '<g class="sdot"><circle cx="' + C + '" cy="' + (C - 143) + '" r="9" fill="url(#hgG)"/><circle cx="' + C + '" cy="' + (C - 143) + '" r="2.6" fill="#fff"/></g></svg>';
  }

  /** ctx: {db, today, goal, sel (subject id), running (active record or null), onToggle, onManual, onAddSubject} -> {el, update} */
  function hero(ctx) {
    var db = ctx.db, running = ctx.running, goal = ctx.goal, w = words();
    var subj = running ? Core.subjectOrGhost(db, running.subject) : (ctx.sel ? Core.subject(db, ctx.sel) : null);
    var refs = {};
    var greet = h('div', { class: 'greet' }, h('small', null, greeting()), refs.display = h('h2', { class: 'display' }, running ? w.run : w.idle));
    refs.clock = h('div', { class: 'clock num' }, I18n.clock(running ? Core.elapsed(db) : 0));
    refs.state = h('div', { class: 'state' + (!running && !subj ? ' none' : '') }, h('i'), h('span', null, running ? t('running') + (subj ? ' · ' + I18n.subjName(subj) : '') : (subj ? I18n.subjName(subj) : t('timer_hint'))));
    refs.sub = h('div', { class: 'core-sub' });
    var orbit = h('div', { class: 'orbit' }, h('div', { class: 'orbit-svg', html: orbitSvg() }), h('div', { class: 'core' }, refs.state, refs.clock, refs.sub));
    var go = h('button', { class: 'go', 'aria-label': running ? t('stop') : t('start'), html: UI.icon(running ? 'stop' : 'play'), onclick: ctx.onToggle });
    var manual = h('button', { class: 'rbtn', 'aria-label': t('add_time'), html: UI.icon('plus'), onclick: ctx.onManual });
    var addSub = h('button', { class: 'rbtn', 'aria-label': t('add_subject'), html: UI.icon('book'), onclick: ctx.onAddSubject });
    var el = h('section', { class: 'hero' + (running ? ' running' : '') }, greet, orbit, h('div', { class: 'ctl' }, manual, go, addSub));

    var tk = el.querySelectorAll('.tk'), arc = el.querySelector('.arc'), glow = el.querySelector('.arc-glow'), cap = el.querySelector('.cap'), sdot = el.querySelector('.sdot');
    var lit = -1, lastTot = -1, litSec = -1;
    function setFrac(f, animate) {
      var off = (CIRC * (1 - f)).toFixed(1), deg = (f * 360).toFixed(1);
      if (!animate) { }
      arc.style.strokeDashoffset = off; glow.style.strokeDashoffset = off; cap.style.transform = 'rotate(' + deg + 'deg)'; cap.style.opacity = f > 0.004 ? 1 : 0;
      if (!animate) { }
    }
    function update() {
      var run = db.active && Core.subject(db, db.active.subject), el_s = run ? Core.elapsed(db) : 0, sec = Math.floor(el_s) % 60;
      refs.clock.textContent = I18n.clock(el_s);
      if (run && sec !== litSec) {                               // the 60 ticks fill up once per minute of the session
        var from = litSec > sec ? 0 : Math.max(litSec, 0);
        if (sec < litSec) for (var i = 0; i < 60; i++) tk[i].classList.remove('on');
        for (var j = from; j <= sec; j++) tk[j].classList.add('on');
        litSec = sec;
      } else if (!run && litSec !== -1) { for (var k = 0; k < 60; k++) tk[k].classList.remove('on'); litSec = -1; }
      sdot.style.opacity = run ? 1 : 0;
      if (run) sdot.style.transform = 'rotate(' + (el_s * 6).toFixed(1) + 'deg)';
      var tot = Core.daySec(db, ctx.today);
      if (tot !== lastTot) {
        lastTot = tot; var f = goal ? Math.min(1, tot / goal) : 0;
        refs.sub.textContent = I18n.dur(tot) + ' · ' + t('of_goal', { goal: I18n.dur(goal) });
        setFrac(f, false); lastFrac = f;
        el.classList.toggle('goal-hit', goal > 0 && tot >= goal);
      }
    }
    // first paint continues from where the ring was, so a re-render never "restarts" it
    setFrac(lastFrac, false);
    litSec = -1; update();
    if (running) { var s0 = Math.floor(Core.elapsed(db)) % 60; sdot.style.transition = 'none'; sdot.style.transform = 'rotate(' + (Core.elapsed(db) * 6).toFixed(1) + 'deg)'; void sdot.getBoundingClientRect(); sdot.style.transition = ''; }
    return { el: el, update: update };
  }

  var ART = { // glyph per kind, drawn with the app's own icon set
    tasks: 'tasks', exams: 'exams', chart: 'stats', subjects: 'book', classes: 'today', entries: 'today'
  };
  function empty(kind, text, hint) {
    var art = h('div', { class: 'art', html:
      '<svg viewBox="0 0 120 120" aria-hidden="true"><defs><radialGradient id="eo" cx=".35" cy=".3" r=".9"><stop offset="0" stop-color="#67E8F9" stop-opacity=".55"/><stop offset=".5" stop-color="#1769FF" stop-opacity=".25"/><stop offset="1" stop-color="#07111F" stop-opacity=".1"/></radialGradient></defs>' +
      '<circle class="r1" cx="60" cy="60" r="56" fill="none" stroke-dasharray="2 7"/><circle class="r2" cx="60" cy="60" r="46" fill="none" stroke-dasharray="40 12 8 12"/>' +
      '<circle cx="60" cy="60" r="34" fill="url(#eo)"/><circle cx="60" cy="60" r="34" fill="none" class="rim2"/></svg>' });
    art.appendChild(h('span', { class: 'glyph', html: UI.icon(ART[kind] || 'info') }));
    return h('div', { class: 'empty-art' }, art, h('div', { class: 't1' }, text), hint ? h('div', { class: 't2' }, hint) : null);
  }

  /** Glowing countdown ring: `days` left, filled over a 30-day window. */
  function countdown(days, label, tone) {
    var size = 112, r = 46, c = 2 * Math.PI * r, f = Math.max(0.04, 1 - Math.min(Math.max(days, 0), 30) / 30);
    var col = tone === 'warn' ? 'var(--amber)' : 'var(--accent)';
    return h('div', { class: 'cd', style: { '--tone': col }, html: '<svg viewBox="0 0 ' + size + ' ' + size + '" width="' + size + '" height="' + size + '"><circle cx="56" cy="56" r="' + r + '" fill="none" class="cd-track" stroke-width="8"/><circle cx="56" cy="56" r="' + r + '" fill="none" class="cd-arc" stroke-width="8" stroke-linecap="round" stroke-dasharray="' + (c * f).toFixed(1) + ' ' + c.toFixed(1) + '" transform="rotate(-90 56 56)"/></svg><div class="cd-n"><b class="num">' + I18n.digits(Math.max(days, 0)) + '</b><span>' + label + '</span></div>' });
  }

  root.Art = { hero: hero, empty: empty, countdown: countdown, greeting: greeting };
})(window);
