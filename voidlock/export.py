"""Export study history to CSV, PDF, and HTML formats."""
import csv
from datetime import datetime, timedelta
from pathlib import Path


def _format_time(seconds):
    """Convert seconds to HH:MM:SS format."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _get_sessions_data(store):
    """Extract all study sessions from history."""
    sessions = []
    for r in store.history:
        try:
            start_time = datetime.fromtimestamp(r["start"])
            duration = int(r.get("focus_sec", 0))
            subject = str(r.get("subject", "")).strip() or "بدون موضوع"
            sessions.append({
                "date": start_time.date().isoformat(),
                "time": start_time.strftime("%H:%M:%S"),
                "subject": subject,
                "duration_sec": duration,
                "duration_str": _format_time(duration)
            })
        except Exception:
            pass
    return sorted(sessions, key=lambda x: (x["date"], x["time"]))


def _calculate_summary(sessions, study_log):
    """Calculate total time and per-subject breakdown."""
    total_seconds = sum(s["duration_sec"] for s in sessions)

    # Add stopwatch entries
    for e in study_log.d.get("entries", []):
        try:
            total_seconds += int(e.get("sec", 0))
        except (TypeError, ValueError):
            pass

    # Per-subject totals
    subject_totals = {}
    for s in sessions:
        subj = s["subject"]
        subject_totals[subj] = subject_totals.get(subj, 0) + s["duration_sec"]

    for e in study_log.d.get("entries", []):
        try:
            sid = e.get("subject")
            if sid:
                subj_obj = study_log.subject(sid)
                if subj_obj:
                    name = subj_obj["name"]
                    subject_totals[name] = subject_totals.get(name, 0) + int(e.get("sec", 0))
        except Exception:
            pass

    return total_seconds, subject_totals


def export_csv(store, study_log, output_path):
    """Export study history to CSV."""
    sessions = _get_sessions_data(store)
    total_seconds, subject_totals = _calculate_summary(sessions, study_log)

    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)

        # Summary
        writer.writerow(['خلاصه کل مطالعه'])
        writer.writerow(['زمان کل', _format_time(total_seconds)])
        writer.writerow([])

        # Per-subject summary
        writer.writerow(['خلاصه هر درس'])
        writer.writerow(['درس', 'زمان'])
        for subj, sec in sorted(subject_totals.items(), key=lambda x: -x[1]):
            writer.writerow([subj, _format_time(sec)])
        writer.writerow([])

        # Session details
        writer.writerow(['جزئیات جلسات'])
        writer.writerow(['تاریخ', 'ساعت', 'درس', 'مدت'])
        for s in sessions:
            writer.writerow([s["date"], s["time"], s["subject"], s["duration_str"]])


def export_html(store, study_log, output_path):
    """Export study history to self-contained HTML."""
    sessions = _get_sessions_data(store)
    total_seconds, subject_totals = _calculate_summary(sessions, study_log)

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>گزارش تاریخچه مطالعه</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
            background: #f5f5f5;
            padding: 20px;
            direction: rtl;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            margin-bottom: 30px;
            font-size: 28px;
            text-align: center;
            border-bottom: 3px solid #3498db;
            padding-bottom: 15px;
        }}
        h2 {{
            color: #34495e;
            margin: 30px 0 15px 0;
            font-size: 22px;
            border-right: 4px solid #3498db;
            padding-right: 10px;
        }}
        .summary-box {{
            background: #ecf0f1;
            padding: 20px;
            border-radius: 6px;
            margin-bottom: 25px;
        }}
        .total-time {{
            font-size: 36px;
            color: #27ae60;
            font-weight: bold;
            text-align: center;
            margin: 15px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th {{
            background: #3498db;
            color: white;
            padding: 12px;
            text-align: right;
            font-weight: bold;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ddd;
        }}
        tr:nth-child(even) {{
            background: #f9f9f9;
        }}
        tr:hover {{
            background: #e8f4f8;
        }}
        .subject-name {{
            font-weight: 600;
            color: #2c3e50;
        }}
        .duration {{
            color: #7f8c8d;
            font-family: 'Courier New', monospace;
        }}
        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            .container {{
                box-shadow: none;
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>گزارش تاریخچه مطالعه</h1>

        <div class="summary-box">
            <h2>خلاصه کل</h2>
            <div class="total-time">{_format_time(total_seconds)}</div>
            <p style="text-align: center; color: #7f8c8d;">مجموع زمان مطالعه</p>
        </div>

        <h2>خلاصه هر درس</h2>
        <table>
            <thead>
                <tr>
                    <th>درس</th>
                    <th>زمان</th>
                </tr>
            </thead>
            <tbody>
"""

    for subj, sec in sorted(subject_totals.items(), key=lambda x: -x[1]):
        html += f"""                <tr>
                    <td class="subject-name">{subj}</td>
                    <td class="duration">{_format_time(sec)}</td>
                </tr>
"""

    html += """            </tbody>
        </table>

        <h2>جزئیات جلسات</h2>
        <table>
            <thead>
                <tr>
                    <th>تاریخ</th>
                    <th>ساعت</th>
                    <th>درس</th>
                    <th>مدت</th>
                </tr>
            </thead>
            <tbody>
"""

    for s in sessions:
        html += f"""                <tr>
                    <td>{s["date"]}</td>
                    <td>{s["time"]}</td>
                    <td class="subject-name">{s["subject"]}</td>
                    <td class="duration">{s["duration_str"]}</td>
                </tr>
"""

    html += """            </tbody>
        </table>
    </div>
</body>
</html>
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)


def export_pdf(store, study_log, output_path):
    """Export study history to PDF using ReportLab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        raise ImportError("ReportLab is required for PDF export. Install with: pip install reportlab")

    sessions = _get_sessions_data(store)
    total_seconds, subject_totals = _calculate_summary(sessions, study_log)

    doc = SimpleDocTemplate(str(output_path), pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    story = []
    styles = getSampleStyleSheet()

    # Title
    title_style = ParagraphStyle('Title', parent=styles['Title'], alignment=2, fontSize=20)
    story.append(Paragraph("Study History Report", title_style))
    story.append(Spacer(1, 0.5*cm))

    # Summary
    story.append(Paragraph(f"<b>Total Time:</b> {_format_time(total_seconds)}", styles['Normal']))
    story.append(Spacer(1, 0.5*cm))

    # Subject summary table
    story.append(Paragraph("<b>Per-Subject Summary</b>", styles['Heading2']))
    subject_data = [['Subject', 'Time']]
    for subj, sec in sorted(subject_totals.items(), key=lambda x: -x[1]):
        subject_data.append([subj, _format_time(sec)])

    subject_table = Table(subject_data, colWidths=[12*cm, 4*cm])
    subject_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(subject_table)
    story.append(Spacer(1, 0.5*cm))

    # Sessions table
    story.append(Paragraph("<b>Session Details</b>", styles['Heading2']))
    session_data = [['Date', 'Time', 'Subject', 'Duration']]
    for s in sessions:
        session_data.append([s["date"], s["time"], s["subject"], s["duration_str"]])

    session_table = Table(session_data, colWidths=[3*cm, 3*cm, 6*cm, 4*cm])
    session_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8)
    ]))
    story.append(session_table)

    doc.build(story)
