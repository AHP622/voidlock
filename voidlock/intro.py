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
    "1.14.72": (
        ["The Daily plans in the HTML report now stop at the last day of the report (the end day you chose, never later than today), so future plans no longer show as not done."],
        ["برنامه‌های روزانه در گزارش HTML حالا تا آخرین روز گزارش نشان داده می‌شوند (روز پایانی که انتخاب کرده‌اید و حداکثر امروز)؛ برنامه‌ی روزهای آینده دیگر به‌عنوان «انجام نشد» دیده نمی‌شود."]),
    "1.14.71": (
        ["On the phone you can now send a report for ANY period: quick buttons (today, 7, 14, 30, 90 days, all) fill the From and To dates, which you can also change freely. The sync server can no longer share its port with another program on Windows."],
        ["روی گوشی حالا می‌توانید گزارش را برای هر بازه‌ی دلخواه بفرستید: دکمه‌های سریع (امروز، ۷، ۱۴، ۳۰، ۹۰ روز و همه) تاریخ «از» و «تا» را پر می‌کنند و می‌توانید هر تاریخی را هم خودتان بگذارید. سرور همگام‌سازی هم روی ویندوز دیگر پورتش را با برنامه‌ی دیگری شریک نمی‌شود."]),
    "1.14.70": (
        ["One-tap weekly report: a button on the phone sends the last 7 days to the share sheet, and on the computer it saves the report and shows its folder. The window now shows the Windows 11 Snap Layouts on the maximize button, a taskbar click minimizes it, and buttons no longer stay lit after the mouse passes quickly."],
        ["گزارش هفتگی با یک لمس: روی گوشی ۷ روز گذشته مستقیم به منوی اشتراک‌گذاری می‌رود و روی کامپیوتر گزارش ذخیره و پوشه‌اش باز می‌شود. روی دکمه‌ی بزرگ‌کردن پنجره حالا چیدمان‌های Snap ویندوز ۱۱ نشان داده می‌شود، کلیک روی آیکون تسک‌بار برنامه را مینیمایز می‌کند و دکمه‌ها بعد از عبور سریع ماوس روشن نمی‌مانند."]),
    "1.14.69": (
        ["The HTML report has a new \"Daily plans\" button: it shows the student's daily to-do lists for the report period, marked done or not done. For a longer period you can pick one day or all days. The sessions table was removed from reports."],
        ["گزارش HTML دکمه‌ی تازه‌ی «برنامه‌ی روزانه» دارد: برنامه‌های روزانه‌ی دانش‌آموز در بازه‌ی گزارش را با وضعیت انجام‌شده یا انجام‌نشده نشان می‌دهد. برای بازه‌ی چندروزه می‌شود یک روز یا همه‌ی روزها را انتخاب کرد. جدول جلسه‌های تمرکز هم از گزارش‌ها حذف شد."]),
    "1.14.68": (
        ["Updates now show a download progress bar with the percentage, then ask whether to install now or later. If you choose later, VOIDLOCK reminds you every 6 hours."],
        ["به‌روزرسانی‌ها حالا نوار پیشرفت و درصد دانلود نشان می‌دهند و بعد می‌پرسند همین حالا نصب شود یا بعداً. اگر «بعداً» را بزنید، هر ۶ ساعت یادآوری می‌شود."]),
    "1.14.67": (
        ["Sidebar tabs no longer stay highlighted after a fast mouse sweep, the gap under the logo is smaller, and the collapse arrow now follows the language."],
        ["تب‌های سایدبار بعد از حرکت سریع ماوس دیگر روشن نمی‌مانند، فاصله‌ی زیر لوگو کمتر شد و فلش جمع‌کردن سایدبار با زبان فارسی هماهنگ شد."]),
    "1.14.66": (
        ["Fixed Persian text in Settings and Help appearing left-aligned; descriptions and help text are right-aligned again."],
        ["متن فارسی در تنظیمات و راهنما که چپ‌چین نمایش داده می‌شد درست شد؛ توضیحات و متن راهنما دوباره راست‌چین هستند."]),
    "1.14.65": (
        ["Restored the Settings and Help layout alignment; Persian descriptions remain right-aligned."],
        ["چیدمان قبلی تنظیمات و راهنما بازگردانده شد و توضیحات فارسی همچنان راست‌چین هستند."]),
    "1.14.64": (
        ["Fixed a startup error in Help and added live download percentage for Windows updates."],
        ["خطای اجرا در بخش راهنما برطرف شد و درصد دانلود زنده برای آپدیت ویندوز اضافه شد."]),
    "1.14.63": (
        ["Windows navigation can collapse to icons, expand manually, or adapt to the window width; the app version and Novum signature stay visible.",
         "Fixed Persian right-to-left alignment in Settings descriptions and Help."],
        ["ناوبری ویندوز می‌تواند فقط آیکون‌ها را نشان دهد، دستی باز شود یا با عرض پنجره هماهنگ شود؛ نسخه و امضای Novum همیشه دیده می‌شوند.",
         "راست‌چین متن‌های فارسی در توضیحات تنظیمات و راهنما اصلاح شد."]),
    "1.14.62": (
        ["Android app icons now match the selected theme. The default daily goal is 10 hours, and a small Exams button jump is fixed.",
         "Windows updates can fall back to the Windows download client if Python's connection to GitHub's file host is reset."],
        ["آیکون اندروید حالا با تم انتخابی برنامه هماهنگ می‌شود. هدف روزانه‌ی پیش‌فرض ۱۰ ساعت شد و پرش دکمه‌ی افزودن آزمون برطرف شد.",
         "اگر اتصال پایتون به میزبان فایل‌های گیت‌هاب قطع شود، به‌روزرسانی ویندوز از دانلودکننده‌ی خود ویندوز کمک می‌گیرد."]),
    "1.14.61": (
        ["Android: a complete visual refresh with a calmer study-focused layout, clearer timer, simpler cards and navigation, and coordinated themes."],
        ["اندروید: بازطراحی کامل رابط با چیدمانی آرام‌تر برای مطالعه، تایمر خواناتر، کارت‌ها و ناوبری ساده‌تر و تم‌های هماهنگ."]),
    "1.14.6": (
        ["Fixed: in the study calendar the highlighted day and its tooltip were far away from the mouse (hundreds of pixels to the right "
         "in the wide card). The day under the pointer is now the one that lights up."],
        ["اصلاح شد: در «تقویم مطالعه» روزی که هایلایت می‌شد و تولتیپش از ماوس فاصله زیادی داشت (در کارت عریض چند صد پیکسل به راست). "
         "حالا همان روزی که زیر ماوس است روشن می‌شود."]),
    "1.14.5": (
        ["Phone only: a new Deep Blue Cinematic look and smoother navigation (tabs keep their scroll position, the timer is untouched, Back returns to the previous tab). "
         "Nothing changes on the computer."],
        ["فقط گوشی: ظاهر جدید «آبی عمیق سینمایی» و ناوبری روان‌تر (هر بخش جای اسکرولش را نگه می‌دارد، تایمر دست‌نخورده است و دکمه‌ی برگشت به بخش قبلی می‌رود). "
         "روی رایانه چیزی تغییر نمی‌کند."]),
    "1.14.4": (
        ["Fixed: the presentation pictures (`--screenshots`) were never saved. Each tab is now shown, painted and saved one after the other, "
         "problems are reported in a log file, and the demo data is now a strong student's panel. Nothing changes for normal use."],
        ["اصلاح شد: عکس‌های معرفی برنامه (`--screenshots`) ذخیره نمی‌شدند. حالا هر تب به‌نوبت نمایش داده، رندر و ذخیره می‌شود، مشکلات در "
         "یک فایل گزارش نوشته می‌شوند و داده‌ی نمایشی پنل یک دانش‌آموز قوی است. برای استفاده‌ی عادی چیزی تغییر نمی‌کند."]),
    "1.14.3": (
        ["Fixed: updating could stop with \u201cCould not read the checksum\u201d when the connection to GitHub was cut (common with a VPN or "
         "a filter). The program now takes the file's checksum from GitHub's release data and, when it has to download it separately, "
         "retries a few times instead of giving up at the first reset."],
        ["اصلاح شد: آپدیت گاهی با پیام «Could not read the checksum» متوقف می‌شد، وقتی اتصال به گیت‌هاب قطع می‌شد (با فیلترشکن یا فیلترینگ "
         "رایج است). حالا برنامه چک‌سام فایل را از اطلاعات ریلیز گیت‌هاب می‌گیرد و اگر لازم شد جدا دانلودش کند، به‌جای تسلیم شدن در "
         "اولین قطعی چند بار دوباره تلاش می‌کند."]),
    "1.14.2": (
        ["Fixed: several texts (including the Overview greeting) were unreadable in the Candy, Paper and Mint themes - they were quietly "
         "stuck on the dark theme's colour no matter which theme was chosen. Found and fixed at the source (a handful of widgets that only "
         "picked up a theme's colour the first time the app ran, not on every theme).",
         "Fixed: hovering the study calendar's little squares could show the wrong day's tooltip (the mouse position and the grid were "
         "measured in opposite directions).",
         "The Overview's daily chart now always runs left to right by date, oldest to newest, like any other chart of a quantity over time.",
         "The Overview's date-range button now also offers \u201cAll time\u201d, and shows the period's daily average next to it."],
        ["اصلاح شد: چند نوشته (از جمله خوش‌آمد نمای کلی) در تم‌های آبنبات، کاغذ و نعنایی خوانا نبودند - بی‌صدا روی رنگ تم تیره گیر کرده "
         "بودند، مهم نبود کدام تم انتخاب شده. ریشه‌اش پیدا و درست شد (چند ویجت که رنگ تم را فقط بار اول اجرای برنامه می‌گرفتند، نه هر بار).",
         "اصلاح شد: رفتن روی مربع‌های کوچک تقویم مطالعه گاهی اطلاعات روز اشتباه را نشان می‌داد (جهت محاسبه‌ی موقعیت موس با جهت ترسیم جدول "
         "یکی نبود).",
         "نمودار مطالعه‌ی روزانه‌ی نمای کلی حالا همیشه از چپ (قدیمی‌تر) به راست (جدیدتر) است، مثل هر نموداری که یک کمیت را در طول زمان نشان می‌دهد.",
         "دکمه‌ی بازه‌ی زمانی نمای کلی حالا «کل زمان‌ها» را هم دارد و میانگین روزانه‌ی همان بازه را کنارش نشان می‌دهد."]),
    "1.14.1": (
        ["Fixed: with the language set to English, the Study Timer and Settings tabs would not open when clicked (a missing name in the "
         "exam-countdown date text raised an error that silently aborted the tab switch, every time)."],
        ["اصلاح شد: وقتی زبان روی انگلیسی بود، با کلیک روی تب‌های «تایمر مطالعه» و «تنظیمات» صفحه عوض نمی‌شد (یک نام ناقص در متن "
         "شمارش‌معکوس آزمون باعث خطایی می‌شد که هر بار بی‌صدا جلوی عوض‌شدن تب را می‌گرفت)."]),
    "1.14.0": (
        ["Weekly classes now sync between the computer and the phone, just like exams and study data: add or edit a class on either one and "
         "it travels with the next sync.",
         "The phone can add, edit and delete classes itself (More ▸ Tasks ▸ Classes), and the phone's report now includes the weekly timetable.",
         "Class and exam reminders, and a notice for new versions, now arrive on the phone as real notifications — even when the app is closed "
         "(turn them on in More ▸ Notifications).",
         "A smoother phone interface: a sliding highlight on switches, a gentle fade when a tab opens, nicer toggle switches, and a Reduce Motion "
         "setting for anyone who prefers fewer animations."],
        ["از این به بعد کلاس‌های هفتگی هم مثل آزمون‌ها و داده‌ی مطالعه بین کامپیوتر و گوشی همگام می‌شوند: کلاس را در هرکدام اضافه یا "
         "ویرایش کنید، با همگام‌سازی بعدی به آن یکی هم می‌رسد.",
         "گوشی هم می‌تواند کلاس اضافه، ویرایش و حذف کند (بیشتر ◂ کارها ◂ کلاس‌ها)، و گزارش گوشی حالا برنامه‌ی هفتگی کلاس‌ها را هم دارد.",
         "یادآوری کلاس و آزمون، و خبر نسخه‌ی تازه، حالا در گوشی به‌صورت اعلان واقعی می‌آیند — حتی وقتی برنامه بسته است (از بیشتر ◂ اعلان‌ها روشن کنید).",
         "رابط گوشی نرم‌تر شد: هایلایت لغزان روی کلیدهای دوتایی، محو شدن ملایم هنگام باز شدن هر تب، کلیدهای روشن/خاموش زیباتر، و یک گزینه‌ی کاهش انیمیشن برای کسانی که حرکت کمتر می‌خواهند."]),
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
