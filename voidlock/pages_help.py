"""Help page: every feature in one place, with search across titles and text."""
from PySide6.QtWidgets import QLineEdit, QVBoxLayout

from . import i18n

from .pages_a import Page
from .theme import T
from .widgets import Card, label

# (tab, title, text). Searched by words in any of the three fields. Persian and English versions of the same topics.
TOPICS_FA = [
    # ---- شروع
    ("شروع", "VOIDLOCK چیه؟", "VOIDLOCK یه نگهبان تمرکزه: برنامه‌ها و سایت‌های حواس‌پرتی رو توی جلسه‌ی مطالعه یا ساعت‌های قفل می‌بنده، "
     "ساعت مطالعه، تست و لغتت رو ثبت می‌کنه، کلاس‌ها و آزمون‌ها رو یادآوری می‌کنه و برای روزهای بدون بازی بهت امتیاز می‌ده."),
    ("شروع", "نصب و داده‌ها", "با VoidLock-Setup.exe نصب کن (بدون نیاز به ادمین) یا فقط VoidLock.exe رو توی یه پوشه‌ی ثابت بذار. داده‌هات "
     "(ساعت‌ها، تست‌ها، تنظیمات، بکاپ‌ها) توی پوشه‌ی %APPDATA%\\VoidLock هستن و با آپدیت، نصب یا جابه‌جایی برنامه دست نمی‌خورن."),
    ("شروع", "پنجره، سینی و شروع با ویندوز", "دکمه‌ی بستن پنجره، برنامه رو کنار ساعت ویندوز (سینی) پنهان می‌کنه تا یادآوری کلاس‌ها و بررسی آپدیت ادامه داشته "
     "باشه. برای خروج کامل از آیکن سینی «Quit» رو بزن. با گزینه‌ی «شروع در سینی همراه ویندوز» (پیش‌فرض خاموش) فقط آیکن سینی بالا میاد و پنجره خودش باز نمی‌شه."),
    # ---- نمای کلی
    ("نمای کلی", "شروع سریع جلسه", "دکمه‌ی Start یه جلسه‌ی تمرکز با مدت و موضوع انتخاب‌شده شروع می‌کنه؛ برنامه‌های فعال‌شده بسته می‌شن. پریست‌ها "
     "(مثلاً «۵۰ دقیقه») یه کلیک برای جلسه‌های تکراری‌ان."),
    ("نمای کلی", "حالت سخت و خروج اضطراری", "Pause و End فقط وقتی کار می‌کنن که حالت سخت خاموش باشه. در حالت سخت فقط «قفل اضطراری» می‌مونه: باید عبارت "
     "تایپی رو بنویسی و چند ثانیه صبر کنی (زمان صبر توی تنظیمات). اگه برنامه گیر کرد: «VoidLock.exe --recover»."),
    ("نمای کلی", "قوانین جلسه فقط زیاد می‌شن", "وقتی جلسه در جریانه، چیزی که مسدوده رو نمی‌شه از «کنترل برنامه‌ها» خاموش کرد؛ فقط می‌شه برنامه‌ی جدید اضافه کرد. "
     "نگهبان هم قوانین هر جلسه رو جدا نگه می‌داره، پس دست‌کاری فایل‌ها فایده‌ای نداره."),
    # ---- تایمر مطالعه
    ("تایمر مطالعه", "کرنومتر درس‌ها", "روی یه درس بزن تا تایمرش شروع بشه و دوباره بزن تا متوقف و ثبت بشه. همزمان فقط یه درس فعاله. اگه برنامه ناگهانی بسته بشه، زمان تا "
     "آخرین لحظه‌ای که زنده بود حساب می‌شه."),
    ("تایمر مطالعه", "گزارش روزانه", "با فلش‌ها به روزهای قبل برو. زیر «زمان مطالعه‌ی این روز» یه نوار رنگی می‌بینی که نشون می‌ده زمان بین درس‌ها چطور تقسیم شده (فقط تایمر "
     "و ورودی دستی؛ جلسه‌های تمرکز جدا حساب می‌شن تا دوبار شمرده نشن). پایین‌ترش تست‌های حل‌شده و (برای درس زبان) لغت‌ها هستن."),
    ("تایمر مطالعه", "تست و لغت", "برای هر درس با − و + و +۱۰ تعداد تست روز رو ثبت کن. درس‌هایی که اسمشون شبیه زبان باشه (English، زبان…) یا موقع ساختن «شمردن لغت» رو "
     "روشن کرده باشی، یه شمارنده‌ی لغت جدا هم دارن؛ جمع سال توی تحلیل‌ها هست."),
    ("تایمر مطالعه", "اضافه یا کم کردن زمان دستی", "پایین گزارش روزانه درس رو انتخاب کن، دقیقه رو تنظیم کن و «Add time» یا «Remove time» رو بزن. کم کردن از جدیدترین "
     "ورودی‌های همون درس در همون روز کم می‌کنه و هیچ‌وقت منفی نمی‌شه."),
    ("تایمر مطالعه", "مدیریت درس‌ها", "«Manage» دکمه‌های ویرایش و حذف رو نشون می‌ده. ویرایش: نام، رنگ، نشون دادن توی «تست‌های حل‌شده» و شمارنده‌ی لغت؛ تغییر اسم هیچ ساعتی رو "
     "از دست نمی‌ده. موقع ساختن درس جدید هم می‌تونی انتخاب کنی توی تست‌ها بیاد یا نه."),
    ("تایمر مطالعه", "درس حذف‌شده", "ساعت‌ها و تست‌های یه درس حذف‌شده پاک نمی‌شن: توی نوار روزانه با اسم قبلی و برچسب «حذف‌شده» می‌مونن. اگه دوباره درسی با همون اسم بسازی، "
     "همه‌ی تاریخچه‌اش به اون برمی‌گرده. برنامه موقع شروع هم از روی بکاپ‌ها ساعت‌های درس‌های دوباره‌ساخته‌شده رو به همنام جدیدشون برمی‌گردونه."),
    ("تایمر مطالعه", "برنامه‌ی روز و روزهای بعد", "کادر «برنامه‌ی امروز» کارهای هر روز رو نگه می‌داره. با فلش‌های کنار عنوان به فردا یا هر روز دیگه برو و برنامه‌اش رو بنویس؛ "
     "با «Today» برمی‌گردی. با کلیک روی ردیف تیکش بزن."),
    ("تایمر مطالعه", "آزمون‌ها", "دکمه‌ی «Exams» بالای این صفحه تو رو به تب «آزمون‌ها» می‌بره. نزدیک‌ترین آزمون با شمارش معکوس اینجا هم نوشته می‌شه، یه روز قبل و در روز آزمون یادآوری "
     "می‌گیری، و توی گزارش روزانه روز آزمون علامت داره."),
    ("آزمون‌ها", "ثبت آزمون و نتیجه", "«Add exam»: اسم و روز آزمون. بعد از برگزاری، «Enter results» رو بزن و درصد و تراز هر درس، تراز کل و رتبه‌ی کل رو وارد کن (ارقام فارسی هم قبوله؛ "
     "هر چی نمی‌دونی خالی بذار). درصد می‌تونه منفی باشه (تا ۳۳-). نتایج بعداً قابل ویرایش یا حذفن."),
    ("آزمون‌ها", "نمودار پیشرفت", "چهار نمودار: تراز کل (با خط روند و بهترین نقطه)، رتبه‌ی کل (پایین‌تر = بهتر؛ محور برعکسه تا بالا رفتن یعنی بهتر شدن)، تراز هر درس و درصد هر درس. "
     "روی نقطه‌ها بمون تا اسم آزمون و عدد رو ببینی. کارت‌های بالا آخرین تراز، بهترین تراز، آخرین رتبه و تغییر نسبت به آزمون قبل رو نشون می‌دن (▲ بهتر، ▼ بدتر)، "
     "و جدول «آخرین آزمون» تراز و درصد هر درس و تغییرش رو می‌گه."),
    ("تایمر مطالعه", "شمارش معکوس کنکور", "تاریخ کنکور رو از تنظیمات (تقویم شمسی) بده؛ شمارش معکوس بالای این صفحه و توی پیام بستن برنامه‌ها میاد."),
    # ---- کنترل برنامه‌ها
    ("کنترل برنامه‌ها", "فعال کردن برنامه‌ها", "هر برنامه‌ای که فعالش کنی، توی جلسه و ساعت‌های قفل بسته می‌شه و یه پیام شخصی می‌بینی. دسته‌ها (بازی، پیام‌رسان، مرورگر…) "
     "جدا هستن و می‌تونی برنامه‌ی دلخواه هم با «Add app» اضافه کنی."),
    ("کنترل برنامه‌ها", "قفل چندروزه", "«Lock» یه برنامه رو چند روز می‌بنده. آزاد کردنش زودتر از موعد یعنی تایپ عبارت و صبر کردن زمان انتظار (تنظیمات). تا وقتی قفلی هست، "
     "زمان انتظار رو فقط می‌شه بیشتر کرد."),
    ("کنترل برنامه‌ها", "سایت‌ها", "سایت‌ها از فایل hosts مسدود می‌شن و به دسترسی ادمین نیاز دارن؛ یه بار «نگهبان مدیر» رو فعال کن. بعد از آپدیت قدیمی ممکنه یه بار از تو "
     "تأیید ویندوز بخواد (برای اینکه نگهبان روی باتری هم راه بیفته)."),
    # ---- جلسه‌ها
    ("جلسه‌های مطالعه", "تاریخچه و پریست‌ها", "همه‌ی جلسه‌های تمرکز با مدت و تعداد برنامه‌های بسته‌شده اینجاست. پریست‌ها رو می‌سازی و ویرایش می‌کنی. خروجی CSV از تنظیمات."),
    # ---- برنامه‌ریزی
    ("برنامه‌ریزی", "کلاس‌ها", "«Add class»: اسم، مکان یا معلم، روزها (چندتا همزمان)، ساعت و مدت. ۱۵ دقیقه قبل از کلاس (قابل تغییر برای هر کلاس) یه کارت یادآوری میاد و "
     "بالای برنامه همیشه «کلاس بعدی: …، X دیگر» نوشته می‌شه. اگه پنجره بسته باشه، نگهبان یادآوری رو نشون می‌ده."),
    ("برنامه‌ریزی", "جلسه‌ی هفتگی", "جلسه‌ی تکراری رو برای چند روز با هم بساز. در زمانش تأیید می‌گیره (یا با «شروع خودکار» بی‌سؤال شروع می‌شه) و اگه برنامه دیر باز شده باشه تا ۳۰ دقیقه "
     "بعدش هم پیشنهاد می‌شه. اگه با کلاس یا جلسه‌ی دیگه هم‌زمان باشه هشدار می‌گیری."),
    ("برنامه‌ریزی", "ساعت‌های قفل", "در ساعت‌های تعیین‌شده (مثلاً ۲۲ تا ۶) دسته‌های انتخابی هر هفته خودکار بسته می‌شن. حذفشون هم مثل قفل چندروزه زمان انتظار داره."),
    ("برنامه‌ریزی", "کارت امروز", "بالای صفحه، کلاس‌ها و جلسه‌های امروز به ترتیب زمان با وضعیت «اکنون»، «X دیگر»، «انجام شد» یا «از دست رفت» می‌آن."),
    # ---- جایزه‌ها
    ("جایزه‌ها", "امتیاز و جایزه", "هر روز بدون بازی امتیاز می‌گیری و هر چند روز پیاپی پاداش اضافه. با امتیاز، زمان بازی، فیلم یا هر جایزه‌ی دلخواه می‌خری. روزهایی که نگهبان "
     "کمتر از یک ساعت زیر نظر بوده حساب نمی‌شن."),
    ("جایزه‌ها", "بلیت بازی", "بلیت بازی یه پاس موقته که بازی‌ها رو آزاد می‌کنه؛ به‌طور پیش‌فرض فقط جمعه‌ها قابل استفاده‌ست (از تنظیمات قابل تغییره). ساعت جمعه از ساعت اینترنتی نگهبان "
     "گرفته می‌شه، پس عوض کردن ساعت ویندوز فایده‌ای نداره."),
    # ---- تحلیل
    ("تحلیل‌ها", "آمار و گزارش", "مطالعه‌ی امروز، هدف روزانه، زنجیره‌ی روزها، نمودار هفتگی، نمای سال (ساعت، تست، لغت)، تقویم مطالعه و گزارش تلاش برای باز کردن بازی‌ها."),
    ("تحلیل‌ها", "گزارش برای مشاور یا والدین", "دکمه‌ی «Export report» بالای صفحه‌ی تحلیل‌ها (یا از تنظیمات ← داده): بازه رو انتخاب کن (روز، هفته، ماه شمسی، سال، همه‌ی زمان‌ها یا دلخواه)، "
     "اسم دانش‌آموز رو بنویس و قالب رو بزن. HTML یه فایل تک‌صفحه‌ایه که همه‌چیزش (CSS و نمودار) داخلشه، راست‌به‌چپ و فارسی، با چاپ تمیز و قابل فرستادن توی تلگرام یا واتس‌اپ. "
     "PDF آماده‌ی چاپه و CSV برای اکسله. گزارش شامل خلاصه، جمع هر درس (با درس‌های حذف‌شده)، نمودار ستونی روزانه به تفکیک درس (با خط هدف، میانگین، میانگین ۷ روزه و علامت روز آزمون)، "
     "الگوی هفتگی مطالعه، جدول روزانه یا ماهانه و جدول جلسه‌های تمرکز است. اگه نتیجه‌ی آزمون ثبت کرده باشی، بخش «نتایج آزمون‌ها و روند تراز» هم میاد (نمودار تراز و رتبه، تراز هر درس، قوی‌ترین و "
     "ضعیف‌ترین درس‌ها، بیشترین پیشرفت و افت)، و «برنامه‌ی هفتگی کلاس‌ها» هم هست تا مشاور بدونه کلاس‌ها کی برگزار می‌شن. هر دو بخش رو می‌شه توی پنجره‌ی خروجی خاموش کرد. "
     "زمان مطالعه همون تعریف تب تایمر رو داره؛ جلسه‌ها جدا فهرست می‌شن تا دوبار شمرده نشن."),
    # ---- تنظیمات
    ("تنظیمات", "تم و صدا", "نُه تم (هفت تیره و دو روشن) با پیش‌نمایش و ده سبک صدا. با تغییر تم، برنامه دوباره راه می‌افته. دکمه‌ی «Test sound» صدا رو پخش می‌کنه."),
    ("تنظیمات", "زبان و تقویم", "فارسی کل برنامه رو راست‌به‌چپ و با تقویم شمسی می‌کنه. زبان با راه‌اندازی دوباره اعمال می‌شه."),
    ("تنظیمات", "بروزرسانی", "برنامه هنگام اجرا و هر چند ساعت از مخزن رسمی (AHP622/voidlock) نسخه‌ی جدید رو بررسی می‌کنه و خبر می‌ده. با «نصب خودکار» وقتی جلسه‌ای در جریان نیست نصب و دوباره "
     "اجرا می‌شه. فایل با SHA-256 تأیید می‌شه؛ اگه دانلود قطع بشه ادامه پیدا می‌کنه."),
    ("تنظیمات", "پشتیبان و خروجی", "هر بار که برنامه شروع یا بسته می‌شه (اگه داده عوض شده باشه) یه بکاپ گرفته می‌شه. از تنظیمات می‌تونی خروجی JSON بگیری، از بکاپ برگردی یا CSV جلسه‌ها رو "
     "بگیری. برگردوندن و ورود داده وسط جلسه بسته‌ست."),
    ("تنظیمات", "نگهبان و باتری", "نگهبان یه پروسه‌ی جدا و محافظ‌شده‌ست که حتی با بسته بودن پنجره کار می‌کنه. از ۱.۴.۰ به بعد هم روی باتری راه می‌افته و بعد از ۷۲ ساعت کشته نمی‌شه."),
    # ---- مشکلات
    ("عیب‌یابی", "برنامه اجرا نمی‌شه (DLL)", "اگه «DLL load failed while importing QtCore» دیدی، «Microsoft Visual C++ Redistributable» رو از aka.ms/vs/17/release/vc_redist.x64.exe نصب کن. "
     "VOIDLOCK ویندوز ۱۰ یا ۱۱ ۶۴ بیتی لازم داره."),
    ("عیب‌یابی", "آپدیت checksum رو رد کرد", "یعنی فایل وسط راه ناقص رسیده (اغلب فیلترشکن یا پروکسی). برنامه خودش تا ۴ بار ادامه یا تکرار می‌کنه؛ اگه نشد VoidLock.exe رو دستی از Releases بگیر."),
    ("میانبرها", "میانبرها", "Ctrl+1 تا Ctrl+9 بین تب‌ها، Ctrl+K جستجو، Ctrl+Enter شروع یا توقف تایمر."),
]

TOPICS_EN = [
    ("Start", "What is VOIDLOCK?", "A focus guard: it closes distracting programs and sites during a study session or lock hours, records your study hours, tests "
     "and words, reminds you of classes and exams, and rewards days without gaming."),
    ("Start", "Install and data", "Install with VoidLock-Setup.exe (no administrator rights) or keep VoidLock.exe in a fixed folder. Your data (hours, tests, settings, "
     "backups) is in %APPDATA%\\VoidLock and is not touched by updating, installing or moving the program."),
    ("Start", "Window, tray and start with Windows", "The window's close button hides VOIDLOCK in the tray (next to the clock) so class reminders and update checks keep working. "
     "Quit from the tray icon. 'Start in the tray with Windows' (off by default) only starts the tray icon - the window never opens by itself."),
    ("Overview", "Quick start", "Start begins a focus session with the chosen length and subject and closes the enabled programs. Presets are one-click recurring sessions."),
    ("Overview", "Strict mode and emergency exit", "Pause and End work only when strict mode is off. In strict mode only the emergency unlock remains: type the phrase and wait "
     "(wait time in Settings). If the program is stuck: 'VoidLock.exe --recover'."),
    ("Overview", "Session rules only grow", "While a session runs you cannot switch a blocked program off in Application Control, only add new ones. The guard also keeps each session's "
     "rules itself, so editing files does not help."),
    ("Study Timer", "Subject stopwatch", "Tap a subject to start its timer, tap again to stop and save. One subject runs at a time. After a crash the time counts until the last moment the program was alive."),
    ("Study Timer", "Daily log", "Use the arrows to visit earlier days. Under 'Study time this day' a coloured bar shows how the time was split between subjects (stopwatch and manual entries only; "
     "focus sessions are counted separately so nothing is counted twice). Below are tests solved and, for language subjects, words learned."),
    ("Study Timer", "Tests and words", "Use -, + and +10 for each subject's tests of the day. Subjects named like a language (English, زبان...) or created with 'Count words' get a separate words counter; "
     "the yearly total is in Analytics."),
    ("Study Timer", "Add or remove time manually", "Pick the subject under the daily log, set the minutes and press Add time or Remove time. Removing takes from the newest entries of that "
     "subject on that day and never goes below zero."),
    ("Study Timer", "Manage subjects", "'Manage' shows edit and delete buttons. Edit: name, colour, whether it appears in 'Tests solved', words counter; renaming keeps all hours. "
     "When adding a subject you also choose whether it gets a tests counter."),
    ("Study Timer", "Deleted subjects", "Hours and tests of a deleted subject are kept: the daily bar shows them with the old name and 'deleted'. Add a subject with the same name again and the whole "
     "history returns to it. At start the program also gives hours of subjects that were deleted and re-created back to the same-name subject, using the backups."),
    ("Study Timer", "Plan for any day", "'Today's plan' keeps tasks per day. Use the arrows next to its title to open tomorrow or any other day and write its plan; 'Today' brings you back. Click a row to tick it."),
    ("Study Timer", "Exams", "The 'Exams' button: add your exam days with a name. The nearest exam with a countdown is shown on this page, you get a reminder the day before and on the day, "
     "and the daily log marks exam days."),
    ("Study Timer", "Exam countdown", "Set the entrance exam date (Jalali) in Settings; the countdown appears at the top of this page and in the 'program closed' message."),
    ("Application Control", "Enabling programs", "Every enabled program is closed during sessions and lock hours with a personal message. Categories are separate and you can add your own program with 'Add app'."),
    ("Application Control", "Multi-day lock", "'Lock' closes a program for several days. Releasing early means typing a phrase and waiting (Settings). While any lock exists the wait can only be made longer."),
    ("Application Control", "Websites", "Sites are blocked through the hosts file and need administrator rights: enable the administrator guard once. After updating from an old version Windows may ask once to refresh it "
     "(so the guard also starts on battery)."),
    ("Study Sessions", "History and presets", "All focus sessions with length and number of programs closed. Build and edit presets. CSV export is in Settings."),
    ("Schedule", "Classes", "'Add class': name, place or teacher, days (several at once), time and length. A reminder card appears 15 minutes before (adjustable per class) and the top bar always shows "
     "'Next class: ... in X'. If the window is closed the guard shows the reminder."),
    ("Schedule", "Weekly sessions", "Create a recurring session for several days at once. It asks for confirmation when due (or starts silently with 'Start automatically') and is still offered up to 30 minutes late. "
     "You get a warning if it overlaps a class or another session."),
    ("Schedule", "Lock hours", "At the chosen hours (say 22:00-06:00) the selected categories are closed every week. Removing them needs the same wait as a multi-day lock."),
    ("Schedule", "Today card", "The top of the page lists today's classes and sessions in order with 'NOW', 'in X', 'DONE' or 'MISSED'."),
    ("Rewards", "Points and rewards", "Each day without gaming earns points, with a bonus for streaks. Spend points on play time, a film or your own rewards. Days the guard watched for less than an hour do not count."),
    ("Rewards", "Play pass", "A play ticket unlocks games for a while; by default only on Fridays (changeable). The day comes from the guard's internet time, so changing the Windows clock does not help."),
    ("Analytics", "Statistics", "Today's study, daily goal, streak, weekly chart, year overview (hours, tests, words), study calendar and the report of attempts to open games."),
    ("Exams", "Exams and results", "'Add exam': name and day. After the exam press 'Enter results' and type the percent and taraz of each subject, the total taraz and the overall rank (Persian digits are fine; leave unknown "
     "values empty). Percent can be negative (down to -33). Results can be edited or removed later."),
    ("Exams", "Progress charts", "Four charts: total taraz (with a trend line and the best point), overall rank (lower is better; the axis is inverted so up always means better), taraz per subject and percent per subject. "
     "Hover a point for the exam name and value. The cards show the latest taraz, best taraz, latest rank and the change from the previous exam (▲ better, ▼ worse); 'Latest exam' lists every subject's percent, taraz and change."),
    ("Analytics", "Report for advisor or parents", "The 'Export report' button at the top of Analytics (or Settings -> Data): choose the period (day, week, Jalali month, year, all time or custom), type the student's name and pick a format. "
     "HTML is one self-contained page (CSS and charts inside), right-to-left Persian or English, clean to print and easy to send by chat. PDF is ready to print and CSV opens in Excel. The report has a summary, time per subject "
     "(deleted subjects included), a stacked daily chart by subject (goal line, average, 7-day average, exam markers), the weekday pattern, a daily or monthly table, the focus-session table, "
     "the exam results and taraz progress (if you recorded any) and the weekly timetable of classes - the last two can be switched off in the export window. Study time uses the Study Timer's definition; sessions are listed separately so nothing is counted twice."),
    ("Settings", "Themes and sounds", "Nine themes (seven dark, two light) with preview cards and ten sound styles. Changing the theme restarts the program. 'Test sound' plays the chosen style."),
    ("Settings", "Language and calendar", "Persian turns the whole interface right-to-left with the Jalali calendar. The language applies after a restart."),
    ("Settings", "Updates", "The program checks the official repository (AHP622/voidlock) at start and every few hours and tells you about a new version. With 'Install automatically' it installs and restarts when no session "
     "is running. The file is verified with SHA-256 and a cut download is resumed."),
    ("Settings", "Backup and export", "A backup is taken when the program starts or closes (if data changed). In Settings: JSON export, restore from a backup, CSV of sessions. Restore and import are closed during a session."),
    ("Settings", "Guard and battery", "The guard is a separate protected process that works even when the window is closed. Since 1.4.0 it also starts on battery and is not killed after 72 hours."),
    ("Troubleshooting", "Program does not start (DLL)", "If you see 'DLL load failed while importing QtCore', install the Microsoft Visual C++ Redistributable from aka.ms/vs/17/release/vc_redist.x64.exe. "
     "VOIDLOCK needs 64-bit Windows 10 or 11."),
    ("Troubleshooting", "Update refused (checksum)", "The file arrived incomplete (often a VPN or proxy). The program resumes or retries up to 4 times; otherwise download VoidLock.exe from Releases."),
    ("Shortcuts", "Shortcuts", "Ctrl+1 to Ctrl+9 switch tabs, Ctrl+K search, Ctrl+Enter start or stop the timer."),
]


def topics():
    return TOPICS_FA if i18n.is_fa() else TOPICS_EN


class HelpPage(Page):
    def __init__(self, ctx):
        super().__init__(ctx, "Help", "Search any feature")
        self.search = QLineEdit()
        self.search.setPlaceholderText("جستجو در راهنما (مثلاً صدا، ادمین، قفل)")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumHeight(40)
        self.search.setStyleSheet(
            f"QLineEdit{{background:{T.panel2}; border:1px solid {T.border}; border-radius:12px;"
            f"padding:6px 14px; color:{T.text}; font-size:13px;}}"
            f"QLineEdit:focus{{border:1px solid {T.cyan};}}")
        self.search.textChanged.connect(self._filter)
        self.body.addWidget(self.search)
        self.list_box = QVBoxLayout()
        self.list_box.setSpacing(12)
        self.body.addLayout(self.list_box)
        self.body.addStretch(1)
        self._cards = []
        self._render(topics())

    def _render(self, topics):
        while self.list_box.count():
            item = self.list_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not topics:
            self.list_box.addWidget(label("چیزی پیدا نشد. کلمه‌ی دیگه‌ای امتحان کن.", 13, color=T.text2))
            return
        for tab, title, text in topics:
            card = Card(pad=16)
            card.lay.addWidget(label(f"{i18n.tr(tab)}  ·  {title}", 13, color=T.cyan))
            card.lay.addWidget(label(text, 12, color=T.text2, wrap=True))
            self.list_box.addWidget(card)

    def _filter(self, text):
        words = [w for w in text.strip().lower().split() if w]
        if not words:
            return self._render(topics())
        hits = []
        for tab, title, body in topics():
            hay = f"{tab} {title} {body}".lower()
            if all(w in hay for w in words):
                hits.append((tab, title, body))
        self._render(hits)

    def on_show(self):
        super().on_show()
        self.search.setFocus()
