/* The phone's small motion layer: durations/easings live in CSS (:root tokens, see app.css), this file does the handful of things CSS alone
 * cannot — positioning the sliding "thumb" behind the selected segmented-control option, and the fade+slide-up when a tab's content is
 * swapped in. Everything here only touches opacity/transform (cheap to animate) and respects Reduced Motion (OS setting or the app's own
 * switch in More ▸ Settings, both read as a single CSS token scale — see setReduced). */
(function (root) {
  'use strict';
  var KEY = 'voidlock.motion';

  function prefersReduced() {
    try { return root.matchMedia && root.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { return false; }
  }
  /** value: true (force on), false (force off), or null/undefined (follow the OS). */
  function setReduced(value) {
    var html = document.documentElement;
    if (value === true) html.setAttribute('data-motion', 'off');
    else if (value === false) html.setAttribute('data-motion', 'on');
    else html.removeAttribute('data-motion');
    try { localStorage.setItem(KEY, value === true ? 'off' : value === false ? 'on' : ''); } catch (e) { /* ignore */ }
  }
  function isReduced() {
    var html = document.documentElement, a = html.getAttribute('data-motion');
    return a === 'off' || (a !== 'on' && prefersReduced());
  }

  /** Positions the sliding pill of every `.seg` under its `.on` button (adds the pill once, moves it on every call). Call after any
   * render that could change which option is selected or the available width. A no-op with nothing to measure yet. */
  var settleTimer = null;
  function layoutSegThumbsSettled(root_) {         // schedules one more measurement once the view-entrance animation has finished moving things
    clearTimeout(settleTimer);
    settleTimer = setTimeout(function () { layoutSegThumbs(root_); }, 320);
  }
  function layoutSegThumbs(root_) {
    (root_ || document).querySelectorAll('.seg').forEach(function (seg) {
      var on = seg.querySelector('button.on');
      var thumb = seg.querySelector(':scope > .thumb');
      if (!on) { if (thumb) thumb.style.opacity = '0'; return; }
      if (!thumb) { thumb = document.createElement('div'); thumb.className = 'thumb'; seg.insertBefore(thumb, seg.firstChild); }
      var first = seg.querySelector('button'); if (!first) return;
      var base = first.getBoundingClientRect(), bx = on.getBoundingClientRect();   // thumb's CSS "left/right:3px" already sits under the first button
      thumb.style.opacity = '1';
      thumb.style.width = bx.width + 'px';
      thumb.style.transform = 'translateX(' + (bx.left - base.left) + 'px)';
    });
  }
  /** Replays the fade+slide-up entrance of #view (e.g. after App.render() swaps the tab's content). */
  function replayViewIn(el) {
    if (!el) return;
    el.classList.remove('v-in');
    void el.offsetWidth;                 // restart the CSS animation
    el.classList.add('v-in');
  }

  if (typeof root.addEventListener === 'function') root.addEventListener('resize', function () { layoutSegThumbs(); });

  root.Motion = { isReduced: isReduced, setReduced: setReduced, layoutSegThumbs: layoutSegThumbs, layoutSegThumbsSettled: layoutSegThumbsSettled, replayViewIn: replayViewIn };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.Motion;
})(typeof window !== 'undefined' ? window : globalThis);
