"""The first-run texts of the computer app (voidlock/intro.py) and the phone's copy (android/.../js/intro.js) must stay complete and in step.
Run:  python tests/intro_texts_test.py     (no Qt needed)"""
import ast
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from voidlock import __version__, i18n, intro  # noqa: E402


def nav_keys():
    src = (ROOT / "voidlock" / "app.py").read_text(encoding="utf-8")
    m = re.search(r"^NAV = (\[.*?\])\n", src, re.S | re.M)
    return [k for k, _t, _i in ast.literal_eval(m.group(1))]


class Texts(unittest.TestCase):
    def test_every_tab_has_a_tip_in_the_order_of_the_sidebar(self):
        self.assertEqual(intro.ORDER, nav_keys())
        for k in intro.ORDER:
            en_t, fa_t, en_p, fa_p = intro.TABS[k]
            self.assertTrue(en_t and fa_t)
            self.assertEqual(len(en_p), len(fa_p), k)
            self.assertTrue(2 <= len(en_p) <= 3, k)
            for p in en_p + fa_p:
                self.assertLess(len(p), 190, "tips must stay short: " + p)

    def test_news_for_this_version(self):
        self.assertIn(__version__, intro.NEWS)
        en, fa = intro.NEWS[__version__]
        self.assertEqual(len(en), len(fa))

    def test_both_languages(self):
        for lang in (False, True):
            i18n.is_fa = (lambda v=lang: v)
            title, pts = intro.tab("exams")
            self.assertTrue(title and pts)
            self.assertIn("Novum", intro.SIGNATURE)
            self.assertTrue(all(intro.t(k) for k in intro.UI))
            self.assertIn(__version__.split(".")[0], intro.t("news", v=__version__).replace("۱", "1") if lang else intro.t("news", v=__version__))
            a, b = intro.welcome_text()
            self.assertTrue(a and b)

    def test_the_phone_has_the_same_tabs_and_news(self):
        js = (ROOT / "android/app/src/main/assets/www/js/intro.js").read_text(encoding="utf-8")
        self.assertIn("'Novum'", js)
        self.assertIn(f"'{__version__}'", js)
        for k in ("today", "stats", "exams", "tasks", "more"):
            self.assertIn(k + ":", js)


if __name__ == "__main__":
    unittest.main(verbosity=2)
