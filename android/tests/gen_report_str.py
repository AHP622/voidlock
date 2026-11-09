"""Regenerates android/app/src/main/assets/www/js/report_str.js from voidlock/report.py (the report texts are the computer's)."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, ROOT)
from voidlock import report  # noqa: E402

out = ("/* Texts of the report: GENERATED from voidlock/report.py (STR). Do not edit by hand: run  python android/tests/gen_report_str.py */\n"
       "(function (root) {\n  'use strict';\n  var STR = " + json.dumps(report.STR, ensure_ascii=False, indent=1, sort_keys=True) + ";\n"
       "  var CSS = " + json.dumps(report._CSS, ensure_ascii=False) + ";\n"
       "  if (typeof module !== 'undefined' && module.exports) module.exports = { STR: STR, CSS: CSS }; else { root.REPORT_STR = STR; root.REPORT_CSS = CSS; }\n})(typeof window !== 'undefined' ? window : globalThis);\n")
path = os.path.join(ROOT, "android", "app", "src", "main", "assets", "www", "js", "report_str.js")
open(path, "w", encoding="utf-8").write(out)
print("written", path)
