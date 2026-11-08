/* Texts (Persian / English), digits and dates. t('key', {var}) ; keys used in the code must exist in both languages (tests check). */
(function (root) {
  'use strict';
  var S = {
    fa: {
      app: 'VOIDLOCK',
      nav_today: 'امروز', nav_stats: 'آمار', nav_exams: 'آزمون‌ها', nav_tasks: 'کارها', nav_more: 'بیشتر',
      today: 'امروز', studied_today: 'مطالعه‌ی امروز', goal: 'هدف', of_goal: 'از هدف {goal}', start: 'شروع', stop: 'پایان', running: 'در حال مطالعه',
      pick_subject: 'یک درس انتخاب کنید', add_time: 'افزودن زمان دستی', minutes: 'دقیقه', hours_short: 'س', min_short: 'د',
      no_subjects: 'هنوز درسی اضافه نشده. یک درس اضافه کنید تا شروع کنید.', add_subject: 'افزودن درس', subject_name: 'نام درس، مثلاً ریاضی',
      by_subject: 'امروز به تفکیک درس', tests_solved: 'تست', words_learned: 'لغت', entries_today: 'ثبت‌های امروز', no_entries: 'امروز هنوز مطالعه‌ای ثبت نشده.',
      delete: 'حذف', cancel: 'انصراف', save: 'ذخیره', add: 'افزودن', edit: 'ویرایش', done: 'تمام', close: 'بستن', yes: 'بله', confirm: 'تأیید', select: 'انتخاب',
      manual_title: 'افزودن زمان مطالعه', how_long: 'چند دقیقه؟', which_day: 'کدام روز؟', subject: 'درس', saved: 'ذخیره شد.',
      stats: 'آمار', last_days: '{n} روز', daily_study: 'مطالعه‌ی روزانه', total: 'جمع', avg_per_day: 'میانگین روزانه', best_day: 'بهترین روز', streak: 'روزهای پیاپی',
      subject_share: 'سهم درس‌ها', other_subjects: 'سایر درس‌ها', daily_goal_line: 'هدف روزانه', exam_day: 'روز آزمون', hours_axis: 'ساعت', study_days: 'روزِ مطالعه',
      exams: 'آزمون‌ها', next_exam: 'آزمون بعدی', days_left: '{n} روز دیگر', today_exam: 'امروز!', days_ago: '{n} روز پیش', no_exams: 'هنوز آزمونی اضافه نشده.',
      add_exam: 'افزودن آزمون', exam_name: 'نام آزمون', exam_date: 'تاریخ', exam_time: 'ساعت (اختیاری)', edit_exam: 'ویرایش آزمون', delete_exam: 'آزمون حذف شود؟',
      enter_results: 'ثبت نتایج', edit_results: 'ویرایش نتایج', results_title: 'نتایج', results_hint: 'آنچه می‌دانید را پر کنید. درصد و تراز برای هر درس است؛ بقیه را خالی بگذارید.',
      total_taraz: 'تراز کل', overall_rank: 'رتبه کل', region_rank: 'رتبه در منطقه', percent: 'درصد', taraz: 'تراز', note_optional: 'یادداشت (اختیاری)',
      remove_result: 'حذف این نتیجه', exam_subjects: 'درس‌های آزمون', exam_subjects_hint: 'درس‌هایی که برایشان نتیجه ثبت می‌کنید. از درس‌های مطالعه جدا هستند.',
      no_exam_subjects: 'هنوز درسی نیست. نام درس را بنویسید و «افزودن» را بزنید.', new_subject: 'درس جدید، مثلاً حسابان', check_numbers: 'اعداد را بررسی کنید: درصد از ۳۳- تا ۱۰۰، تراز تا ۲۰۰۰۰، رتبه ۱ یا بیشتر.',
      progress: 'روند نتایج', k_taraz: 'تراز کل', k_rank: 'رتبه کل', k_region: 'رتبه منطقه', k_subjects: 'تراز درس‌ها', k_percent: 'درصد درس‌ها', rank_hint: 'پایین‌تر = بهتر',
      no_results_yet: 'نتیجه‌ای ثبت نشده تا نمودار رسم شود.', rank_word: 'رتبه', region_word: 'منطقه',
      tasks: 'کارها', add_task: 'کار جدید…', open_before: 'مانده از قبل', no_tasks: 'کاری برای این روز نیست.', tomorrow: 'فردا',
      more: 'بیشتر', sync: 'هماهنگی', settings: 'تنظیمات', subjects: 'درس‌های مطالعه', edit_subject: 'ویرایش درس', delete_subject: 'درس حذف شود؟',
      delete_subject_msg: '«{name}» از لیست برداشته می‌شود. ساعت‌های ثبت‌شده برایش می‌مانند.', color: 'رنگ', custom_color: 'رنگ دلخواه', choose_colour: 'انتخاب رنگ',
      colour_lifted: 'مشکی و سفید کمی روشن‌تر می‌شوند تا دیده شوند.',
      sync_card: 'هماهنگی با کامپیوتر', sync_intro: 'همه‌ی اطلاعات (درس‌ها، زمان‌ها، آزمون‌ها، کارها و تاریخچه) بین گوشی و VOIDLOCK کامپیوتر یکسان می‌شود.',
      wifi: 'وای‌فای', wifi_hint: 'گوشی و کامپیوتر باید روی یک شبکه باشند (مودم، حتی سیم‌کارتی، یا هات‌اسپات گوشی). اینترنت لازم نیست.',
      find_computer: 'پیدا کردن کامپیوتر', finding: 'در حال جستجو…', computers_found: 'کامپیوترهای پیداشده', none_found: 'کامپیوتری پیدا نشد. مطمئن شوید VOIDLOCK روی کامپیوتر باز است و «هماهنگی روی وای‌فای» روشن است و هر دو روی یک شبکه‌اند.',
      enter_address: 'یا آدرس را دستی بنویسید', address_ph: 'مثلاً 192.168.1.20:47821', connect: 'اتصال', enter_code: 'کد ۶ رقمی نمایش‌داده‌شده روی کامپیوتر', pair: 'جفت‌شدن',
      paired_with: 'جفت‌شده با {name}', sync_now: 'هماهنگی همین حالا', unpair: 'فراموش‌کردن کامپیوتر', last_sync: 'آخرین هماهنگی', never: 'هنوز نشده', auto_sync: 'هماهنگی خودکار وقتی برنامه باز است',
      st_ok: 'هماهنگ است', st_busy: 'در حال هماهنگی…', st_err: 'کامپیوتر در دسترس نیست', st_off: 'جفت نشده', synced_ok: 'هماهنگ شد.', up_to_date: 'همه‌چیز به‌روز است.',
      wrong_code: 'کد درست نیست.', no_code: 'روی کامپیوتر «جفت‌کردن گوشی» را بزنید تا کد نمایش داده شود.', locked: 'چند بار اشتباه زدید؛ چند دقیقه صبر کنید.', pair_ok: 'جفت شد.',
      needs_review: 'این هماهنگی بخش بزرگی از داده‌های کامپیوتر را حذف می‌کرد و انجام نشد. از فایل هماهنگی استفاده کنید تا کامپیوتر اول بپرسد.',
      file_sync: 'هماهنگی با فایل', file_hint: 'اگر وای‌فای در دسترس نیست: فایل را ذخیره یا بفرستید (بلوتوث، پیام‌رسان…) و روی دستگاه دیگر وارد کنید.',
      save_file: 'ذخیره / ارسال فایل', import_file: 'ورود فایل هماهنگی', file_saved: 'فایل آماده شد.', import_q: 'فایل هماهنگی وارد شود؟', import_btn: 'ورود',
      from: 'از', new_here: 'جدید در اینجا', changed: 'تغییر کرده', removed_here: 'حذف‌شده از اینجا', big_remove: 'این کار بخش بزرگی از داده‌های این دستگاه را حذف می‌کند. مطمئن شوید فایل و دستگاه درست است.',
      k_entries: 'ثبت مطالعه', k_subjects_n: 'درس', k_exams_n: 'آزمون', k_exam_subjects_n: 'درس آزمون', k_todos_n: 'کار', k_sessions_n: 'جلسه‌ی تمرکز', k_counts: 'شمارش روزانه‌ی تست / لغت',
      language: 'زبان', persian: 'فارسی', english: 'English', daily_goal: 'هدف روزانه (دقیقه)', theme: 'تم', theme_ocean: 'اقیانوس', theme_void: 'تیره', theme_midnight: 'نیمه‌شب', theme_paper: 'روشن',
      about: 'درباره', version: 'نسخه', check_update: 'بررسی به‌روزرسانی', checking: 'در حال بررسی…', update_available: 'نسخه‌ی {v} آماده است', update_none: 'نسخه‌ی شما به‌روز است.',
      update_install: 'دانلود و نصب', update_dl: 'در حال دانلود… {p}٪', update_verify: 'بررسی امضای فایل…', update_need_perm: 'برای نصب باید به VOIDLOCK اجازه‌ی «نصب برنامه‌های ناشناس» بدهید. بعد از دادن اجازه دوباره بزنید.',
      update_failed: 'به‌روزرسانی انجام نشد: {err}', update_auto: 'بررسی خودکار به‌روزرسانی', update_hint: 'به‌روزرسانی از GitHub گرفته می‌شود و فقط با امضای درست نصب می‌شود.',
      weekdays_short: 'ی د س چ پ ج ش', sun_first: '', reset_data: 'پاک‌کردن همه‌ی داده‌های گوشی', reset_q: 'همه‌ی داده‌های این گوشی پاک شود؟', reset_msg: 'اگر قبلاً با کامپیوتر هماهنگ کرده باشید، می‌توانید دوباره از آن بگیرید.',
      from_laptop: 'دریافت از لپ‌تاپ', start_fresh: 'شروع از صفر', welcome: 'خوش آمدید', welcome_msg: 'اگر قبلاً VOIDLOCK را روی کامپیوتر استفاده کرده‌اید، اطلاعاتتان را از آن بگیرید.',
      working: 'لطفاً صبر کنید…', network_error: 'اتصال برقرار نشد.', unknown_error: 'خطای ناشناخته', copy_code: 'کد را روی کامپیوتر ببینید', hours_total: '{h} ساعت', deleted: '(حذف‌شده)',
      today_total_h: 'جمع', sessions_note: 'شامل جلسه‌های تمرکز کامپیوتر', sec: 'ثانیه', pick_date: 'تاریخ', year: 'سال', month: 'ماه', day: 'روز', name: 'نام',
      err_not_sync: 'این فایل یک فایل هماهنگی VOIDLOCK نیست.', err_version: 'این فایل با نسخه‌ی دیگری از VOIDLOCK ساخته شده. هر دو دستگاه را به‌روز کنید.',
      err_same: 'این فایل را همین دستگاه ساخته است.', err_nodev: 'این فایل هماهنگی شناسه‌ی دستگاه ندارد.', err_nodata: 'این فایل داده‌ای ندارد.',
      unauthorized: 'کامپیوتر این گوشی را نمی‌شناسد. دوباره جفت کنید.', paired_phone_name: 'نام این گوشی', retry: 'تلاش دوباره', manual_pair: 'جفت‌کردن دستی',
      group_tests: 'درس‌های تستی', group_words: 'لغت (زبان)',
      pair_confirm_msg: 'روی کامپیوتر باید همین عدد را ببینید. اگر همین بود، آنجا «اجازه» را بزنید؛ اگر عدد فرق داشت، «رد» را بزنید.', waiting_allow: 'منتظر اجازه‌ی شما روی کامپیوتر…', sas_number: 'عدد تأیید',
      pair_denied: 'کامپیوتر اجازه نداد.', pair_expired: 'زمان تمام شد. دوباره امتحان کنید.', pair_key: 'کلید رمزنگاری با کامپیوتر یکی نشد. دوباره جفت کنید.',
      proto_old: 'برنامه‌ی کامپیوتر قدیمی است. هر دو دستگاه را به آخرین نسخه به‌روز کنید.',
      report: 'گزارش', report_make: 'ساخت گزارش…', report_title: 'گزارش مطالعه', report_hint: 'گزارش مطالعه و آزمون‌ها را به‌صورت صفحه‌ی وب، PDF یا فایل اکسل (CSV) بگیرید.', generated: 'تهیه‌شده در',
      r_7: '۷ روز', r_14: '۱۴ روز', r_30: '۳۰ روز', r_90: '۹۰ روز', r_all: 'همه', r_custom: 'دلخواه', r_from: 'از تاریخ', r_to: 'تا تاریخ', fmt_html: 'صفحه‌ی وب (HTML)', fmt_pdf: 'PDF (چاپ)', fmt_csv: 'اکسل (CSV)',
      col_time: 'زمان', col_share: 'سهم', col_avg_day: 'میانگین در روزِ مطالعه', weekly_bars: 'هر ستون یک هفته', report_ready: 'گزارش آماده شد.', report_empty: 'در این بازه داده‌ای نیست.',
      bg_sync: 'هماهنگی در پس‌زمینه (حدود هر ۱۵ دقیقه)', bg_hint: 'وقتی برنامه بسته است هم گاهی با کامپیوتر هماهنگ می‌شود (فقط وقتی هر دو روی یک شبکه باشند). اندروید زمان دقیق را تعیین می‌کند.',
      vpn_hint: 'اگر فیلترشکن روشن است: در فیلترشکن گزینه‌ی «دسترسی به شبکه‌ی محلی (LAN)» را مجاز کنید، یا آن را روی کامپیوتر/گوشی خاموش کنید.',
      unknown_subject: 'درس نامشخص',
      avg: 'میانگین', over_goal: 'بیش از هدف', no_data: 'داده‌ای نیست.', enter_name: 'یک نام بنویسید.', name_taken: 'این نام قبلاً هست.', timer_hint: 'زمان‌سنج با بسته‌شدن برنامه هم ادامه دارد.'
    },
    en: {
      app: 'VOIDLOCK',
      nav_today: 'Today', nav_stats: 'Stats', nav_exams: 'Exams', nav_tasks: 'Tasks', nav_more: 'More',
      today: 'Today', studied_today: 'Studied today', goal: 'Goal', of_goal: 'of {goal} goal', start: 'Start', stop: 'Stop', running: 'Studying',
      pick_subject: 'Pick a subject', add_time: 'Add time by hand', minutes: 'minutes', hours_short: 'h', min_short: 'm',
      no_subjects: 'No subjects yet. Add one to get started.', add_subject: 'Add subject', subject_name: 'Subject name, e.g. Math',
      by_subject: 'Today by subject', tests_solved: 'Tests', words_learned: 'Words', entries_today: 'Entries today', no_entries: 'No study logged today yet.',
      delete: 'Delete', cancel: 'Cancel', save: 'Save', add: 'Add', edit: 'Edit', done: 'Done', close: 'Close', yes: 'Yes', confirm: 'Confirm', select: 'Select',
      manual_title: 'Add study time', how_long: 'How many minutes?', which_day: 'Which day?', subject: 'Subject', saved: 'Saved.',
      stats: 'Stats', last_days: '{n} days', daily_study: 'Daily study', total: 'Total', avg_per_day: 'Daily average', best_day: 'Best day', streak: 'Streak (days)',
      subject_share: 'Subject share', other_subjects: 'Other subjects', daily_goal_line: 'Daily goal', exam_day: 'exam day', hours_axis: 'h', study_days: 'days studied',
      exams: 'Exams', next_exam: 'Next exam', days_left: 'in {n} days', today_exam: 'Today!', days_ago: '{n} days ago', no_exams: 'No exams yet.',
      add_exam: 'Add exam', exam_name: 'Exam name', exam_date: 'Date', exam_time: 'Time (optional)', edit_exam: 'Edit exam', delete_exam: 'Delete this exam?',
      enter_results: 'Enter results', edit_results: 'Edit results', results_title: 'Results', results_hint: 'Fill in what you know. Percent and taraz are per subject; leave the rest empty.',
      total_taraz: 'Total taraz', overall_rank: 'Overall rank', region_rank: 'Region rank', percent: 'Percent', taraz: 'Taraz', note_optional: 'Note (optional)',
      remove_result: 'Remove this result', exam_subjects: 'Exam subjects', exam_subjects_hint: 'The subjects you enter results for. They are separate from the study subjects.',
      no_exam_subjects: 'No subjects yet. Type a name and press Add.', new_subject: 'New subject, e.g. Calculus', check_numbers: 'Check the numbers: percent from -33 to 100, taraz up to 20000, rank 1 or more.',
      progress: 'Progress', k_taraz: 'Total taraz', k_rank: 'Overall rank', k_region: 'Region rank', k_subjects: 'Taraz by subject', k_percent: 'Percent by subject', rank_hint: 'lower = better',
      no_results_yet: 'No results yet, so there is nothing to chart.', rank_word: 'Rank', region_word: 'Region',
      tasks: 'Tasks', add_task: 'New task…', open_before: 'Left from before', no_tasks: 'No tasks for this day.', tomorrow: 'Tomorrow',
      more: 'More', sync: 'Sync', settings: 'Settings', subjects: 'Study subjects', edit_subject: 'Edit subject', delete_subject: 'Delete subject?',
      delete_subject_msg: '“{name}” is removed from the list. The hours logged for it stay.', color: 'Colour', custom_color: 'Custom colour', choose_colour: 'Choose a colour',
      colour_lifted: 'Black and white are lifted a little so they stay visible.',
      sync_card: 'Sync with the computer', sync_intro: 'Everything (subjects, study time, exams, tasks and history) is kept identical between this phone and VOIDLOCK on your computer.',
      wifi: 'Wi-Fi', wifi_hint: 'Phone and computer must be on the same network (a modem, even a SIM modem, or the phone’s hotspot). No internet needed.',
      find_computer: 'Find computer', finding: 'Searching…', computers_found: 'Computers found', none_found: 'No computer found. Make sure VOIDLOCK is open on the computer and “Sync with the phone over Wi-Fi” is on.',
      enter_address: 'Or type the address', address_ph: 'e.g. 192.168.1.20:47821', connect: 'Connect', enter_code: 'The 6-digit code shown on the computer', pair: 'Pair',
      paired_with: 'Paired with {name}', sync_now: 'Sync now', unpair: 'Forget computer', last_sync: 'Last sync', never: 'not yet', auto_sync: 'Sync automatically while the app is open',
      st_ok: 'In sync', st_busy: 'Syncing…', st_err: 'Computer not reachable', st_off: 'Not paired', synced_ok: 'Synced.', up_to_date: 'Everything is up to date.',
      wrong_code: 'That code is not right.', no_code: 'On the computer press “Pair a phone” so a code is shown.', locked: 'Too many wrong tries; wait a few minutes.', pair_ok: 'Paired.',
      needs_review: 'This sync would have removed a lot of the computer’s data, so it was not done. Use a sync file so the computer asks first.',
      file_sync: 'Sync with a file', file_hint: 'If Wi-Fi is not available: save or send the file (Bluetooth, a messenger…) and import it on the other device.',
      save_file: 'Save / send file', import_file: 'Import sync file', file_saved: 'File ready.', import_q: 'Import this sync file?', import_btn: 'Import',
      from: 'From', new_here: 'New here', changed: 'Changed', removed_here: 'Removed here', big_remove: 'This would remove a lot of what is on this device. Check that this is the right file and the right device.',
      k_entries: 'study records', k_subjects_n: 'subjects', k_exams_n: 'exams', k_exam_subjects_n: 'exam subjects', k_todos_n: 'tasks', k_sessions_n: 'focus sessions', k_counts: 'daily test / word counts',
      language: 'Language', persian: 'فارسی', english: 'English', daily_goal: 'Daily goal (minutes)', theme: 'Theme', theme_ocean: 'Ocean', theme_void: 'Dark', theme_midnight: 'Midnight', theme_paper: 'Light',
      about: 'About', version: 'Version', check_update: 'Check for updates', checking: 'Checking…', update_available: 'Version {v} is available', update_none: 'You are up to date.',
      update_install: 'Download and install', update_dl: 'Downloading… {p}%', update_verify: 'Verifying the file…', update_need_perm: 'To install, allow VOIDLOCK to “install unknown apps”. Then press the button again.',
      update_failed: 'The update failed: {err}', update_auto: 'Check for updates automatically', update_hint: 'Updates come from GitHub and are installed only with a correct signature.',
      weekdays_short: 'S M T W T F S', sun_first: '1', reset_data: 'Erase all data on this phone', reset_q: 'Erase all data on this phone?', reset_msg: 'If you synced with the computer before, you can get it back from there.',
      from_laptop: 'Get from the computer', start_fresh: 'Start fresh', welcome: 'Welcome', welcome_msg: 'If you already use VOIDLOCK on a computer, get your data from it.',
      working: 'Please wait…', network_error: 'Could not connect.', unknown_error: 'Unknown error', copy_code: 'See the code on the computer', hours_total: '{h} hours', deleted: '(deleted)',
      today_total_h: 'Total', sessions_note: 'includes focus sessions from the computer', sec: 'sec', pick_date: 'Date', year: 'Year', month: 'Month', day: 'Day', name: 'Name',
      err_not_sync: 'That file is not a VOIDLOCK sync file.', err_version: 'This sync file was made by a different version of VOIDLOCK. Update both devices.',
      err_same: 'This file was made by this same device.', err_nodev: 'That sync file has no device id.', err_nodata: 'The file has no data.',
      unauthorized: 'The computer does not know this phone. Pair again.', paired_phone_name: 'This phone’s name', retry: 'Try again', manual_pair: 'Pair manually',
      group_tests: 'Test subjects', group_words: 'Words (languages)',
      pair_confirm_msg: 'The computer must show the same number. If it does, press “Allow” there; if the number is different, press “Deny”.', waiting_allow: 'Waiting for you to allow it on the computer…', sas_number: 'Confirmation number',
      pair_denied: 'The computer did not allow it.', pair_expired: 'Time ran out. Try again.', pair_key: 'The encryption key did not match the computer. Pair again.',
      proto_old: 'The computer app is out of date. Update both devices to the latest version.',
      report: 'Report', report_make: 'Create report…', report_title: 'Study report', report_hint: 'Get a report of your study and exams as a web page, a PDF or a spreadsheet (CSV).', generated: 'generated',
      r_7: '7 days', r_14: '14 days', r_30: '30 days', r_90: '90 days', r_all: 'All', r_custom: 'Custom', r_from: 'From', r_to: 'To', fmt_html: 'Web page (HTML)', fmt_pdf: 'PDF (print)', fmt_csv: 'Spreadsheet (CSV)',
      col_time: 'Time', col_share: 'Share', col_avg_day: 'Average per study day', weekly_bars: 'one bar per week', report_ready: 'Report ready.', report_empty: 'There is no data in this period.',
      bg_sync: 'Sync in the background (about every 15 minutes)', bg_hint: 'Even when the app is closed it syncs with the computer now and then (only when both are on the same network). Android decides the exact time.',
      vpn_hint: 'If a VPN is on: allow “local network (LAN) access” in the VPN, or turn it off on the computer / phone.',
      unknown_subject: 'Unknown subject',
      avg: 'Average', over_goal: 'Over the goal', no_data: 'No data.', enter_name: 'Type a name.', name_taken: 'That name already exists.', timer_hint: 'The timer keeps running when the app is closed.'
    }
  };
  var lang = 'fa';
  var FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹';
  function t(key, vars) {
    var s = (S[lang] && S[lang][key]) || S.en[key] || key;
    if (vars) Object.keys(vars).forEach(function (k) { s = s.split('{' + k + '}').join(String(vars[k])); });
    return s;
  }
  function digits(s) { s = String(s); return lang === 'fa' ? s.replace(/[0-9]/g, function (d) { return FA_DIGITS[+d]; }) : s; }
  function num(n, dec) {
    if (n === null || n === undefined || isNaN(n)) return '-';
    var s = dec ? Number(n).toFixed(dec) : String(Math.round(n));
    var neg = s[0] === '-'; if (neg) s = s.slice(1);
    var p = s.split('.'); p[0] = p[0].replace(/\B(?=(\d{3})+(?!\d))/g, lang === 'fa' ? '٬' : ',');
    s = p.join(lang === 'fa' ? '٫' : '.');
    return digits((neg ? (lang === 'fa' ? '\u200E-' : '-') : '') + s);
  }
  function dur(sec) {
    sec = Math.max(0, Math.round(sec)); var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60);
    if (!h && !m) return digits(sec ? '<1' : '0') + ' ' + t('min_short');
    return (h ? digits(h) + ' ' + t('hours_short') + (m ? ' ' : '') : '') + (m ? digits(m) + ' ' + t('min_short') : '');
  }
  function clock(sec) {
    sec = Math.max(0, Math.floor(sec)); var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
    function p(n) { return (n < 10 ? '0' : '') + n; }
    return p(h) + ':' + p(m) + ':' + p(s);        // always left-to-right, Latin digits (it sits in a dir=ltr box)
  }
  var fmtCache = {};
  function fmt(opts, locale) { var k = locale + JSON.stringify(opts); return fmtCache[k] || (fmtCache[k] = new Intl.DateTimeFormat(locale, opts)); }
  function loc() { return lang === 'fa' ? 'fa-IR-u-ca-persian-nu-arab'.replace('-nu-arab', '') : 'en-GB'; }
  function dateStr(dk, withWeekday) {
    var d = typeof dk === 'string' ? Core.parseDkey(dk) : dk;
    if (lang === 'fa') {
      var o = fmt({ day: 'numeric', month: 'long', weekday: withWeekday ? 'long' : undefined }, 'fa-IR-u-ca-persian').format(d);
      return o;
    }
    return fmt({ day: 'numeric', month: 'short', weekday: withWeekday ? 'short' : undefined }, 'en-GB').format(d);
  }
  function dayShort(dk) {
    var d = Core.parseDkey(dk);
    if (lang === 'fa') { var j = Jalali.toJalali(d.getFullYear(), d.getMonth() + 1, d.getDate()); return digits(j.jd); }
    return String(d.getDate());
  }
  function monthShort(dk) {
    var d = Core.parseDkey(dk);
    return fmt({ month: 'short' }, lang === 'fa' ? 'fa-IR-u-ca-persian' : 'en-GB').format(d);
  }
  function dateTimeStr(sec) {
    var d = new Date(sec * 1000);
    return dateStr(d, false) + ' · ' + digits(('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2));
  }
  function subjName(s) { return !s ? '?' : (s.name === '?' ? t('unknown_subject') : s.name); }
  function setLang(l) { lang = l === 'en' ? 'en' : 'fa'; if (typeof document !== 'undefined') { document.documentElement.lang = lang; document.documentElement.dir = lang === 'fa' ? 'rtl' : 'ltr'; } }
  var I18n = { S: S, t: t, digits: digits, num: num, dur: dur, clock: clock, dateStr: dateStr, dayShort: dayShort, monthShort: monthShort, dateTimeStr: dateTimeStr,
               setLang: setLang, subjName: subjName, get lang() { return lang; } };
  if (typeof module !== 'undefined' && module.exports) module.exports = I18n; else root.I18n = I18n;
})(typeof window !== 'undefined' ? window : globalThis);
