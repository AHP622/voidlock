"""Help page: every feature in one place, with search across titles and text."""
from PySide6.QtWidgets import QLineEdit, QVBoxLayout

from .pages_a import Page
from .theme import T
from .widgets import Card, label

# (tab, title, text). Searched by words in any of the three fields.
TOPICS = [
    ("Overview", "شروع سریع جلسه", "دکمه Start روی نمای کلی یه جلسه‌ی تمرکز با مدت و موضوع ذخیره‌شده‌ی برنامه‌ریزی شروع می‌کنه. پریست‌ها هم یه کلیک برای جلسه‌های تکراری‌اند."),
    ("Overview", "خروج زودهنگام", "Pause و End فقط وقتی فعال‌ان که حالت سخت خاموش باشه. با حالت سخت فقط قفل اضطراری با عبارت تایپی و زمان انتظار جلسه رو می‌بنده."),
    ("Study Timer", "تایمر مطالعه", "تایمر مطالعه یه کرنومتر دستیه. موضوع رو انتخاب کن، Start رو بزن و بعد Stop. زمان ثبت می‌شه. ورودی دستی هم می‌شه اضافه کرد."),
    ("Study Timer", "to-do امروز", "برای هر روز می‌تونی کار اضافه کنی و با کلیک روی ردیف تیکش بزنی. کلیک روی سطل زباله حذفش می‌کنه."),
    ("Application Control", "قفل برنامه‌ها", "برنامه‌هایی که باید در جلسه بسته بشن رو اینجا فعال کن. هنگام اجرا، VOIDLOCK بسته‌شون می‌کنه و یه پیام شخصی نشون می‌ده."),
    ("Application Control", "قفل چندروزه", "قفل چندروزه یه برنامه رو تا تاریخ مشخصی می‌بنده. برای آزاد کردنش باید آزادسازی رو انجام بدی و زمان انتظار رو صبر کنی."),
    ("Application Control", "مسدودسازی وب", "سایت‌ها از طریق فایل hosts مسدود می‌شن و این نیاز به دسترسی ادمین داره. از تنظیمات ادمین رو فعال کن؛ یه بار کافیه."),
    ("Study Sessions", "جلسه‌های مطالعه", "تاریخچه‌ی همه‌ی جلسه‌ها اینجاست. می‌تونی جلسه‌ی دستی اضافه کنی و مدت هر جلسه رو ویرایش کنی."),
    ("Schedule", "برنامه‌ی هفتگی", "قفل ساعتی هر هفته رو اینجا تعریف کن. در ساعت قفل، برنامه‌های انتخابی بسته می‌شن."),
    ("Rewards", "جایزه‌ها", "با تمرکز امتیاز جمع می‌کنی و با امتیاز می‌تونی زمان بازی یا تماشا بخری. هزینه‌ی هر جایزه داخل خودش نوشته شده."),
    ("Analytics", "آمار و گزارش", "مطالعه‌ی امروز، هدف روزانه، آزمون‌های سال، زنجیره‌ی روزها، نمودار هفتگی و تقویم مطالعه. گزارش تلاش برای بازی هم اینجاست."),
    ("Analytics", "هدف روزانه", "هدف روزانه رو تو تنظیمات تعیین می‌کنی. نوار نمای کلی و آمار تحلیل‌ها بر اساس همین هدف درصد نشون می‌دن."),
    ("Settings", "حالت سخت", "حالت سخت پیش‌فرض رو اینجا تنظیم کن. وقتی روشنه، Pause و End غیرفعال می‌شن."),
    ("Settings", "دسترسی ادمین", "برای مسدودسازی وب و بستن برنامه‌های ادمین لازمه. دکمه‌ی فعال‌سازی ادمین رو بزن و یه بار تأیید کن."),
    ("Settings", "صدا", "صدای بستن برنامه، زنگ و پایان جلسه رو اینجا انتخاب کن. اگه صدایی نمی‌شنوی، حالت صدا رو روی نرم یا زنگ بذار."),
    ("Settings", "پشتیبان‌گیری و خروجی", "تنظیمات و داده‌ها رو می‌تونی خروجی JSON بگیری یا از فایل پشتیبان برگردونی. خروجی CSV جلسه‌ها هم از همین قسمته."),
    ("Settings", "زبان و تقویم", "زبان برنامه و تاریخ کنکور از تنظیمات عوض میشن. تاریخ کنکور توی پیام بستن برنامه‌ها هم می‌آد."),
    ("Settings", "بروزرسانی", "بررسی بروزرسانی و نصب خودکار از تنظیمات قابل فعال یا غیرفعال کردنه."),
    ("Shortcuts", "میانبرها", "Ctrl+1 تا Ctrl+9 بین تب‌ها جابه‌جا می‌کنن، Ctrl+K جستجو، Ctrl+Enter شروع یا توقف تایمر."),
]


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
        self._render(TOPICS)

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
            card.lay.addWidget(label(f"{tab}  ·  {title}", 13, color=T.cyan))
            card.lay.addWidget(label(text, 12, color=T.text2, wrap=True))
            self.list_box.addWidget(card)

    def _filter(self, text):
        words = [w for w in text.strip().lower().split() if w]
        if not words:
            return self._render(TOPICS)
        hits = []
        for tab, title, body in TOPICS:
            hay = f"{tab} {title} {body}".lower()
            if all(w in hay for w in words):
                hits.append((tab, title, body))
        self._render(hits)

    def on_show(self):
        super().on_show()
        self.search.setFocus()
