/* First-run help: a welcome, a short tour of the tabs, a small tip card the first time each tab is opened, and a "What's new" sheet after an
 * update. All texts are here (Persian and English) and are meant to be short. The computer app has the same idea in voidlock/intro.py. */
(function (root) {
  'use strict';
  var SIGN = 'Novum';
  var COPY = {
    ui: {
      fa: { welcome: 'به VOIDLOCK خوش آمدید 👋', tour: 'تور کوتاه برنامه', next: 'بعدی', back: 'قبلی', done: 'تمام', skip: 'بستن', gotIt: 'فهمیدم', hideTips: 'نمایش ندادن راهنما',
            tips: 'راهنمای کوتاه هر بخش', replay: 'دیدن دوباره‌ی تور', news: 'تازه‌ها', newsTitle: 'تازه‌های نسخه‌ی {v}', madeBy: 'ساخته‌شده توسط', step: 'مرحله {i} از {n}', ok: 'باشه' },
      en: { welcome: 'Welcome to VOIDLOCK 👋', tour: 'Quick tour', next: 'Next', back: 'Back', done: 'Done', skip: 'Close', gotIt: 'Got it', hideTips: 'Hide tips',
            tips: 'Short tips for each tab', replay: 'Replay the tour', news: "What's new", newsTitle: "What's new in v{v}", madeBy: 'Made by', step: 'Step {i} of {n}', ok: 'OK' }
    },
    welcome: {
      fa: { intro: 'VOIDLOCK همراه مطالعه و تمرکز شماست: زمان هر درس را ثبت کنید، تست و لغت بشمارید، آزمون‌ها و پیشرفتتان را ببینید و با نسخه‌ی کامپیوتر همگام بمانید.',
            wish: 'برایتان تمرکز، پشتکار و موفقیت آرزو می‌کنم؛ هر روز یک قدم، و نتیجه‌اش می‌آید. 🌟' },
      en: { intro: 'VOIDLOCK is your study and focus companion: time every subject, count tests and words, follow your exams and progress, and stay in sync with the computer app.',
            wish: 'Wishing you focus, perseverance and every success. One step a day, and the results will come. 🌟' }
    },
    tabs: {
      today: { icon: 'today', fa: { title: 'امروز', points: ['روی یک درس بزنید تا کرنومتر شروع شود؛ زمان خودکار ثبت می‌شود.', 'حلقه‌ی هدف نشان می‌دهد امروز چقدر به هدفتان رسیده‌اید.', 'زمان فراموش‌شده را دستی اضافه کنید و تعداد تست و لغت‌های امروز را بشمارید.'] },
               en: { title: 'Today', points: ['Tap a subject to start its timer; the time is saved for you.', 'The goal ring shows how close you are to today’s goal.', 'Add forgotten time by hand and count today’s tests and words.'] } },
      stats: { icon: 'stats', fa: { title: 'آمار', points: ['نمودار مطالعه‌ی هر روز به تفکیک درس، با خط هدف.', 'مجموع، میانگین، بهترین روز و روزهای پیاپی را یک‌جا ببینید.', 'سهم هر درس از کل زمان مطالعه.'] },
               en: { title: 'Stats', points: ['A chart of every day, split by subject, with your goal line.', 'Total, average, best day and streak in one place.', 'The share of each subject in your study time.'] } },
      exams: { icon: 'exams', fa: { title: 'آزمون‌ها', points: ['تاریخ آزمون‌های پیش رو را ثبت کنید و شمارش معکوس را ببینید.', 'بعد از آزمون، تراز کل، رتبه‌ی کل، رتبه‌ی منطقه و درصد و تراز هر درس را وارد کنید.', 'نمودار پیشرفت خودکار ساخته می‌شود. درس‌های آزمون را خودتان تعریف می‌کنید و از درس‌های مطالعه جدا هستند.'] },
               en: { title: 'Exams', points: ['Add your coming exams and watch the countdown.', 'After an exam enter the total taraz, overall rank, region rank and each subject’s percent and taraz.', 'The progress charts are built for you. Exam subjects are your own, separate from the study subjects.'] } },
      tasks: { icon: 'tasks', fa: { title: 'کارها', points: ['کارهای هر روز را بنویسید و با یک ضربه انجام‌شده کنید.', 'کارهای انجام‌نشده‌ی روزهای قبل با برچسب «مانده از قبل» می‌مانند.'] },
               en: { title: 'Tasks', points: ['Write each day’s tasks and tick them with one tap.', 'Unfinished tasks of earlier days stay with the label “Left from before”.'] } },
      more: { icon: 'more', fa: { title: 'بیشتر', points: ['همگام‌سازی با کامپیوتر: از طریق Wi-Fi یا فایل؛ ارتباط خودش دوباره برقرار می‌شود.', 'گزارش مطالعه (PDF، صفحه‌ی وب یا اکسل) دقیقاً مثل گزارش کامپیوتر.', 'درس‌ها، تنظیمات، به‌روزرسانی و درباره‌ی برنامه.'] },
               en: { title: 'More', points: ['Sync with the computer over Wi-Fi or a file; the connection restores itself.', 'The study report (PDF, web page or spreadsheet), the same as the computer’s.', 'Subjects, settings, updates and about.'] } }
    },
    order: ['today', 'stats', 'exams', 'tasks', 'more'],
    news: {
      '1.14.0': {
        fa: ['کلاس‌ها حالا با کامپیوتر همگام می‌شوند و خودتان هم می‌توانید اینجا کلاس اضافه کنید (کارها ◂ کلاس‌ها).',
             'گزارش شما حالا برنامه‌ی هفتگی کلاس‌ها را هم دارد.',
             'یادآوری کلاس و آزمون و خبر نسخه‌ی تازه به‌صورت اعلان واقعی می‌آیند؛ در بیشتر ◂ اعلان‌ها روشنشان کنید.',
             'رابط کمی نرم‌تر و شیک‌تر شد؛ در تنظیمات می‌توانید انیمیشن‌ها را هم کم کنید.'],
        en: ['Classes now sync with the computer, and you can add classes here too (Tasks ▸ Classes).',
             'Your report now includes the weekly class timetable.',
             'Class and exam reminders and new-version notices arrive as real notifications; turn them on in More ▸ Notifications.',
             'A smoother interface, plus a Reduce Motion setting if you prefer fewer animations.']
      },
      '1.13.2': {
        fa: ['شماره‌ی نسخه با برنامه‌ی کامپیوتر یکی شد (اصلاح دونات «نمای کلی» کامپیوتر). در گوشی تغییر دیگری نیست.'],
        en: ['The version number now matches the computer app (donut fix there). No other changes on the phone.']
      },
      '1.13.1': {
        fa: ['شماره‌ی نسخه با برنامه‌ی کامپیوتر یکی شد (اصلاحات «نمای کلی» کامپیوتر). در گوشی تغییر دیگری نیست.'],
        en: ['The version number now matches the computer app (Overview fixes there). No other changes on the phone.']
      },
      '1.13.0': {
        fa: ['برنامه‌ی کامپیوتر «نمای کلی» تازه‌ای با داشبورد و نمودارها دارد. این نسخه‌ی گوشی هم‌شماره‌ی آن است و تغییر دیگری ندارد.'],
        en: ['The computer app has a new Overview dashboard with charts. This phone version carries the same number and has no other changes.']
      },
      '1.12.0': {
        fa: ['گزارش گوشی حالا دقیقاً مثل گزارش کامپیوتر است: همان بخش‌ها، نمودارها و جدول‌ها؛ نام شما هم روی آن نوشته می‌شود.', 'اگر آدرس کامپیوتر عوض شود (مثلاً بعد از چند ساعت)، گوشی خودش دوباره آن را پیدا می‌کند؛ دیگر لازم نیست جفت‌شدن را پاک کنید و از اول وصل کنید.',
             'معرفی کوتاه هر بخش هنگام اولین ورود، و یک تور خوش‌آمد.', 'همین صفحه: بعد از هر به‌روزرسانی، تغییرات را کوتاه می‌بینید.'],
        en: ['The phone’s report is now exactly the computer’s report: the same sections, charts and tables, with your name on it.', 'If the computer’s address changes (for example after a few hours) the phone finds it again by itself; no more deleting the pairing and starting over.',
             'A short tip the first time you open each tab, and a welcome tour.', 'This page: after every update you see a short list of what changed.']
      }
    }
  };
  function lang() { return root.I18n && I18n.lang === 'en' ? 'en' : 'fa'; }
  function U(k, v) { var s = COPY.ui[lang()][k] || COPY.ui.en[k] || k; if (v) Object.keys(v).forEach(function (n) { s = s.replace('{' + n + '}', I18n.digits(v[n])); }); return s; }
  function h() { return UI.h.apply(null, arguments); }
  function list(points) { return h('ul', { class: 'intro-list' }, points.map(function (p) { return h('li', null, p); })); }
  function version() { return String(root.Native && Native.appVersion ? Native.appVersion() : ((root.VOIDLOCK_CONFIG || {}).version || '')); }
  function signature() { return h('div', { class: 'intro-sign', dir: 'ltr' }, SIGN); }

  var touring = false;

  // ---- the welcome (first run): greeting, a wish, the signature, a way to the tour
  function welcomeBody(msg, onTour) {
    var w = COPY.welcome[lang()];
    return h('div', { class: 'intro' },
      h('p', { class: 'intro-p' }, w.intro), h('p', { class: 'intro-p dim' }, msg || ''), h('p', { class: 'intro-wish' }, w.wish), signature(),
      onTour ? h('button', { class: 'btn block', style: { marginTop: '12px' }, onclick: onTour }, U('tour')) : null);
  }

  // ---- the tour: one step per tab, the app shows that tab behind the sheet
  function tour(App) {
    var i = 0, n = COPY.order.length, first = App.view;
    touring = true;
    var s = UI.sheet({ title: null, body: null, onClose: function () { touring = false; markAllSeen(App); App.go(first === 'more' ? 'today' : first); } });
    function draw() {
      var k = COPY.order[i], c = COPY.tabs[k][lang()];
      App.go(k);
      s.body.innerHTML = '';
      s.body.appendChild(h('div', { class: 'intro' },
        h('div', { class: 'small dim' }, U('step', { i: i + 1, n: n })),
        h('h2', { style: { margin: '4px 0 8px' } }, UI.ic(COPY.tabs[k].icon), ' ', c.title), list(c.points),
        h('div', { class: 'actions', style: { display: 'flex', gap: '10px', marginTop: '14px' } },
          h('button', { class: 'btn', style: { flex: 1 }, disabled: i === 0, onclick: function () { i--; draw(); } }, U('back')),
          i < n - 1 ? h('button', { class: 'btn primary', style: { flex: 1 }, onclick: function () { i++; draw(); } }, U('next'))
                    : h('button', { class: 'btn primary', style: { flex: 1 }, onclick: function () { s.close(); } }, U('done')))));
    }
    draw();
  }

  // ---- a tip card on top of a tab, the first time it is opened
  function markAllSeen(App) { var st = App.db.settings; st.tips_seen = st.tips_seen || {}; COPY.order.forEach(function (k) { st.tips_seen[k] = 1; }); App.save(); }
  function attachTip(host, App) {
    var st = App.db.settings, k = App.view, c = COPY.tabs[k];
    if (touring || !c || st.tips === false || (st.tips_seen && st.tips_seen[k]) || App.bg || (!st.welcomed && !App.db.subjects.length && !App.db.entries.length)) return;
    var d = c[lang()];
    var card = h('section', { class: 'card tip' },
      h('div', { class: 'row sb' }, h('b', null, d.title), h('button', { class: 'icon-btn', 'aria-label': U('skip'), onclick: function () { dismiss(false); }, html: '×' })),
      list(d.points),
      h('div', { class: 'row', style: { gap: '8px', marginTop: '6px' } },
        h('button', { class: 'btn sm primary', onclick: function () { dismiss(false); } }, U('gotIt')),
        h('button', { class: 'btn sm', onclick: function () { dismiss(true); } }, U('hideTips'))));
    function dismiss(all) { st.tips_seen = st.tips_seen || {}; st.tips_seen[k] = 1; if (all) st.tips = false; App.save(); card.remove(); }
    host.insertBefore(card, host.firstChild);
  }

  // ---- what's new, after an update
  function newsFor(v) { return COPY.news[v] || COPY.news[Object.keys(COPY.news).sort().pop()]; }
  function whatsNew(App) {
    var v = version(), items = newsFor(v)[lang()];
    var s = UI.sheet({ title: U('newsTitle', { v: v }), body: [h('div', { class: 'intro' }, list(items), signature())],
      actions: [h('button', { class: 'btn primary', onclick: function () { s.close(); } }, U('ok'))] });
    return s;
  }
  function afterBoot(App) {
    var st = App.db.settings, v = version();
    if (!v || st.seen_version === v) return;
    var hasData = App.db.subjects.length || App.db.entries.length || App.db.sync.laptop;
    st.seen_version = v; App.save();
    if (!st.welcomed && !hasData) return;                      // a brand-new install: the welcome is shown instead
    if (!COPY.news[v]) return;                                 // no notes for this exact version: stay quiet
    whatsNew(App);
  }
  function settingsRows(App) {
    var st = App.db.settings, box = h('input', { type: 'checkbox' }); box.checked = st.tips !== false;
    box.addEventListener('change', function () { st.tips = box.checked; if (box.checked) st.tips_seen = {}; App.save(); });
    return [h('label', { class: 'row sb', style: { padding: '12px 0 0' } }, h('span', null, U('tips')), box),
            h('div', { class: 'row', style: { gap: '8px', marginTop: '10px', flexWrap: 'wrap' } },
              h('button', { class: 'btn', onclick: function () { tour(App); } }, U('replay')), h('button', { class: 'btn', onclick: function () { whatsNew(App); } }, U('news')))];
  }
  root.Intro = { SIGN: SIGN, COPY: COPY, welcomeBody: welcomeBody, tour: tour, attachTip: attachTip, whatsNew: whatsNew, afterBoot: afterBoot, settingsRows: settingsRows, signature: signature, U: U };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.Intro;
})(typeof window !== 'undefined' ? window : globalThis);
