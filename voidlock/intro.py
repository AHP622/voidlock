"""First-run help for the computer app: a welcome, a short tour of the tabs, a tip the first time each tab is opened and a
"What's new" page after an update. Only texts and small helpers live here (no Qt), so they are easy to test and to keep in step with
the phone app (android/.../js/intro.js has the same idea)."""
from . import i18n

SIGNATURE = "Novum"

# order of the tour = order of the sidebar
ORDER = ["overview", "study", "apps", "sessions", "schedule", "exams", "rewards", "analytics", "settings", "help"]

UI = {
    "welcome": ("Welcome to VOIDLOCK", "به VOIDLOCK خوش آمدید"),
    "tour": ("Take the quick tour", "تور کوتاه برنامه"),
    "skip": ("Not now", "فعلاً نه"),
    "next": ("Next", "بعدی"),
    "skip_tour": ("Skip the tour", "رد کردن تور"),
    "done": ("Done", "تمام"),
    "got_it": ("Got it", "فهمیدم"),
    "tips_off": ("Turn tips off", "خاموش‌کردن راهنما"),
    "step": ("Step {i} of {n}", "مرحله {i} از {n}"),
    "news": ("What's new in v{v}", "تازه‌های نسخه‌ی {v}"),
    "ok": ("OK", "باشه"),
    "replay": ("Take the tour again", "دیدن دوباره‌ی تور"),
    "whats_new": ("What's new", "تازه‌ها"),
    "made_by": ("Made by", "ساخته‌شده توسط"),
}

WELCOME = {
    "en": ("VOIDLOCK keeps you focused: it closes the games and programs you choose, times your study, tracks your exams and progress "
           "and keeps your phone in sync.",
           "Wishing you focus, perseverance and every success. One step a day, and the results will come."),
    "fa": ("VOIDLOCK تمرکز شما را حفظ می‌کند: بازی‌ها و برنامه‌های انتخابی را می‌بندد، زمان مطالعه را ثبت می‌کند، آزمون‌ها و پیشرفتتان را "
           "نشان می‌دهد و با گوشی همگام می‌ماند.",
           "برایتان تمرکز، پشتکار و موفقیت آرزو می‌کنم؛ هر روز یک قدم، و نتیجه‌اش می‌آید."),
}

# (title en, title fa, points en, points fa)
TABS = {
    "overview": (
        "Overview", "نمای کلی",
        ["Start a focus session in one click: pick the minutes and VOIDLOCK closes the games and apps you chose.",
         "The big status card tells you honestly whether blocking is really working.",
         "Strict mode locks the session until the end; only the emergency unlock (typed phrase + wait) can stop it."],
        ["با یک کلیک جلسه‌ی تمرکز شروع کنید: مدت را بزنید تا بازی‌ها و برنامه‌های انتخاب‌شده بسته شوند.",
         "کارت وضعیت صادقانه می‌گوید قفل واقعاً کار می‌کند یا نه.",
         "حالت سخت جلسه را تا آخر قفل می‌کند؛ فقط خروج اضطراری (تایپ عبارت + انتظار) آن را می‌شکند."]),
    "study": (
        "Study Timer", "تایمر مطالعه",
        ["Tap a subject to start its stopwatch; the time is saved by day.",
         "Count tests and words, add or remove time by hand, plan any day and watch the exam countdown.",
         "The daily goal ring and your streak keep you going."],
        ["روی یک درس بزنید تا کرنومتر شروع شود؛ زمان هر روز ذخیره می‌شود.",
         "تست و لغت بشمارید، زمان را دستی کم و زیاد کنید، برنامه‌ی هر روز را بنویسید و شمارش معکوس کنکور را ببینید.",
         "حلقه‌ی هدف روزانه و روزهای پیاپی (استریک) انگیزه می‌دهند."]),
    "apps": (
        "Application Control", "کنترل برنامه‌ها",
        ["Turn on the games and programs to block during sessions; add your own.",
         "The lock icon closes an app for several days, even without a session. A lock can be extended, never shortened.",
         "Websites can be blocked too (this needs administrator rights)."],
        ["بازی‌ها و برنامه‌هایی را که باید در جلسه بسته شوند روشن کنید؛ برنامه‌ی خودتان را هم اضافه کنید.",
         "آیکن قفل، برنامه را چند روز بسته نگه می‌دارد، حتی بدون جلسه؛ قفل فقط تمدید می‌شود و کوتاه نمی‌شود.",
         "سایت‌ها را هم می‌شود مسدود کرد (به دسترسی ادمین نیاز دارد)."]),
    "sessions": (
        "Study Sessions", "جلسه‌های مطالعه",
        ["The history of your focus sessions, with the time you really stayed focused.",
         "Presets make your favourite session lengths one click away."],
        ["تاریخچه‌ی جلسه‌های تمرکز، با زمان تمرکز واقعی.",
         "پریست‌ها مدت‌های محبوب شما را یک‌کلیکی می‌کنند."]),
    "schedule": (
        "Schedule", "برنامه‌ریزی",
        ["Put your weekly classes and study sessions on the timetable; when it is time you are reminded and start with one click.",
         "Lock hours close the games you choose automatically at set times, every week.",
         "The Today card shows what comes next."],
        ["کلاس‌ها و جلسه‌های هفتگی را در برنامه بنویسید؛ زمانش که شد یادآوری می‌شوید و با یک کلیک شروع می‌کنید.",
         "ساعت‌های قفل، بازی‌های انتخابی را هر هفته در ساعت مقرر خودکار می‌بندند.",
         "کارت امروز نشان می‌دهد بعدی چیست."]),
    "exams": (
        "Exams", "آزمون‌ها",
        ["Add your exams and, after each one, enter the total taraz, overall rank, region rank and each subject's percent and taraz.",
         "Progress charts and the comparison with the previous exam are built for you.",
         "Exam subjects are your own, separate from the study timer's subjects."],
        ["آزمون‌ها را ثبت کنید و بعد از هر آزمون تراز کل، رتبه‌ی کل، رتبه‌ی منطقه و درصد و تراز هر درس را وارد کنید.",
         "نمودار پیشرفت و مقایسه با آزمون قبل خودکار ساخته می‌شود.",
         "درس‌های آزمون را خودتان تعریف می‌کنید و از درس‌های تایمر مطالعه جدا هستند."]),
    "rewards": (
        "Rewards", "جایزه‌ها",
        ["Days without gaming earn points; seven clean days in a row earn a bonus.",
         "Spend points on rewards or on a timed play pass; the rules are yours to set."],
        ["روزهای بدون بازی امتیاز می‌گیرند و هفت روز پیاپی جایزه‌ی ویژه دارد.",
         "امتیازها را خرج جایزه یا بلیت بازی زمان‌دار کنید؛ قانون‌ها دست خودتان است."]),
    "analytics": (
        "Analytics", "تحلیل‌ها",
        ["Study and focus statistics by week, month and year, with a calendar heat map.",
         "Make a report for your advisor or parents: PDF, web page or Excel, with charts and exam results."],
        ["آمار مطالعه و تمرکز هفتگی، ماهانه و سالانه، با نقشه‌ی گرمایی تقویم.",
         "گزارش برای مشاور یا والدین بسازید: PDF، صفحه‌ی وب یا اکسل، با نمودار و نتایج آزمون."]),
    "settings": (
        "Settings", "تنظیمات",
        ["Theme, sounds and language (English or Persian with the Jalali calendar).",
         "Updates, backups, export / import, sync with your phone and the guard's administrator mode.",
         "An update never resets your data."],
        ["تم، صدا و زبان (انگلیسی یا فارسی با تقویم جلالی).",
         "به‌روزرسانی، پشتیبان‌گیری، خروجی و ورودی، همگام‌سازی با گوشی و حالت ادمین نگهبان.",
         "به‌روزرسانی هرگز داده‌های شما را پاک نمی‌کند."]),
    "help": (
        "Help", "راهنما",
        ["Search any topic; every feature is explained in a few short steps.",
         "The buttons on top replay this tour and show what is new."],
        ["هر موضوعی را جست‌وجو کنید؛ هر قابلیت با چند مرحله‌ی کوتاه توضیح داده شده.",
         "دکمه‌های بالا این تور را دوباره نشان می‌دهند و تازه‌ها را مرور می‌کنند."]),
}

NEWS = {
    "1.13.2": (
        ["The subject donut was drawn from the wrong starting angle and left a dark gap: it is now a closed ring that starts at the top, "
         "with only a hairline between the colours.",
         "The little chart of a card that has no data yet is a faint dashed line instead of a coloured block."],
        ["دونات سهم درس‌ها از زاویه‌ی اشتباه شروع می‌شد و یک شکاف تیره می‌گذاشت: حالا حلقه‌ی بسته‌ای است که از بالا شروع می‌شود "
         "و بین رنگ‌ها فقط یک خط باریک است.",
         "نمودار کوچک کارتی که هنوز داده ندارد، به‌جای یک بلوک رنگی، یک خط‌چین کم‌رنگ است."]),
    "1.13.1": (
        ["The Overview now fits any window width: cards re-flow into fewer columns and nothing is cut off at the edge.",
         "A cleaner subject donut, brighter chart columns, a stronger glow, and a header with a greeting card, today's goal and the start square.",
         "For presentations: `VoidLock.exe --home <empty folder> --screenshots <folder>` saves a picture of every tab with demo data."],
        ["نمای کلی با هر عرض پنجره‌ای جور می‌شود: کارت‌ها در ستون‌های کمتر جابه‌جا می‌شوند و چیزی از لبه بیرون نمی‌زند.",
         "دونات سهم درس‌ها تمیزتر، ستون‌های نمودار روشن‌تر، درخشش قوی‌تر، و بالای صفحه با کارت خوش‌آمد، هدف امروز و مربع شروع جلسه.",
         "برای معرفی برنامه: دستور `VoidLock.exe --home <پوشه‌ی خالی> --screenshots <پوشه>` از هر تب با داده‌ی نمایشی عکس می‌گیرد."]),
    "1.13.0": (
        ["A new Overview: a small start-session square in the corner, headline cards, a clean daily chart, the share of each subject, "
         "recent sessions, what is coming up and the protection status.",
         "Every tab got the same glass look: softer cards and a gentle glow behind the window.",
         "Pick 7, 30 or 90 days for the charts; the quick-start presets are in the arrow of the start square."],
        ["نمای کلی جدید: یک مربع کوچک شروع جلسه در گوشه، کارت‌های خلاصه، نمودار روزانه‌ی تمیز، سهم هر درس، جلسه‌های اخیر، "
         "پیش رو و وضعیت محافظت.",
         "همه‌ی تب‌ها ظاهر شیشه‌ای یکدست گرفتند: کارت‌های نرم‌تر و درخششی ملایم پشت پنجره.",
         "بازه‌ی نمودارها را ۷، ۳۰ یا ۹۰ روز انتخاب کنید؛ پریست‌های شروع سریع توی فلش مربع شروع هستند."]),
    "1.12.0": (
        ["The phone's report is now exactly this computer's report: the same sections, charts and tables.",
         "The phone finds this computer again by itself when its address changes, so there is no more \"forget and pair again\".",
         "A short tip the first time you open each tab, a welcome tour, and this What's new page after every update.",
         "A more exact Jalali calendar for dates after 1407 (it is the same as the phone's now)."],
        ["گزارش گوشی حالا دقیقاً مثل گزارش همین کامپیوتر است: همان بخش‌ها، نمودارها و جدول‌ها.",
         "وقتی آدرس کامپیوتر عوض شود، گوشی خودش دوباره آن را پیدا می‌کند و دیگر لازم نیست «فراموش کن و دوباره جفت کن».",
         "معرفی کوتاه هر بخش هنگام اولین ورود، یک تور خوش‌آمد و همین صفحه‌ی تازه‌ها بعد از هر به‌روزرسانی.",
         "تقویم جلالی دقیق‌تر برای تاریخ‌های بعد از ۱۴۰۷ (حالا با گوشی یکی است)."]),
}


def fa():
    return i18n.is_fa()


def t(key, **kw):
    en, fa_ = UI[key]
    s = fa_ if fa() else en
    for k, v in kw.items():
        s = s.replace("{" + k + "}", i18n.digits(v) if fa() else str(v))
    return s


def welcome_text():
    intro, wish = WELCOME["fa" if fa() else "en"]
    return intro, wish


def tab(key):
    """(title, [points]) of a tab in the current language, or None."""
    row = TABS.get(key)
    if not row:
        return None
    return (row[1], row[3]) if fa() else (row[0], row[2])


def news_for(version):
    """Bullet points for this version (or the newest known notes), in the current language."""
    row = NEWS.get(version) or NEWS[sorted(NEWS)[-1]]
    return row[1] if fa() else row[0]


def is_new_user(store, study):
    """A fresh install: nothing was ever studied, focused or locked here."""
    try:
        return not (store.history or study.d.get("entries") or store.active_locks() or store.settings.get("intro_done"))
    except Exception:
        return False
