"""
مقرأة تسميع القرآن الكريم — النسخة الذكية الكاملة
الألوان: أرجواني وذهبي | الميزات: استيراد تلقائي، قائمة انتظار، دعم المواليد
التشغيل: streamlit run maqraa.py
"""

import streamlit as st
import sqlite3, json, os, re
from datetime import datetime, date

# ─── إعداد الصفحة ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="مقرأة التسميع الذكية",
    page_icon="🕌",
    layout="centered",
    initial_sidebar_state="expanded",
)

# التنسيق الجديد (أرجواني وذهبي) بناءً على ذوقك في الجرافيك
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Cairo', sans-serif !important; direction: rtl; }
h1, h2, h3 { font-family: 'Cairo', sans-serif !important; }

/* الألوان الجديدة */
:root {
    --gold: #D4AF37;
    --purple: #4B0082;
    --light-purple: #F3E5F5;
}

/* Header */
.hdr {
    background: linear-gradient(135deg, #4B0082, #6A0DAD);
    padding: 20px;
    border-radius: 15px;
    text-align: center;
    margin-bottom: 25px;
    border-bottom: 4px solid var(--gold);
}
.hdr h1 { color: var(--gold); font-size: 26px; margin: 0; }
.hdr p  { color: #E6E6FA; font-size: 14px; margin-top: 5px; }

/* Waiting Card */
.waiting-card {
    background: #fff;
    border-right: 6px solid var(--purple);
    border-radius: 10px;
    padding: 15px;
    margin-bottom: 12px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    border: 1px solid #eee;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

/* Metric Cards */
.metric-card {
    background: #fff; border-radius: 12px; padding: 20px; text-align: center; 
    border: 1px solid var(--light-purple); box-shadow: 0 2px 8px rgba(75, 0, 130, 0.1);
}
.metric-num { font-size: 35px; font-weight: 700; color: var(--purple); }
.metric-lbl { font-size: 12px; color: #888; margin-top: 4px; }

/* Exam row */
.exam-row {
    background: #fff;
    border-right: 4px solid var(--purple);
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 8px;
    border-top: 1px solid #eee; border-bottom: 1px solid #eee; border-left: 1px solid #eee;
}
.exam-row.fail { border-right-color: #E24B4A; }

/* Badges */
.badge-pass { background:#E8F5E9; color:#2E7D32; padding:4px 12px; border-radius:20px; font-size:13px; font-weight:600; }
.badge-fail { background:#FFEBEE; color:#C62828; padding:4px 12px; border-radius:20px; font-size:13px; font-weight:600; }

/* Error tags */
.tag-ht { background:#FFF9C4; color:#F57F17; padding:3px 10px; border-radius:6px; font-size:12px; margin:2px; display:inline-block; }
.tag-hr { background:#FFF3E0; color:#BF360C; padding:3px 10px; border-radius:6px; font-size:12px; margin:2px; display:inline-block; }
.tag-tt { background:#E3F2FD; color:#1565C0; padding:3px 10px; border-radius:6px; font-size:12px; margin:2px; display:inline-block; }
.tag-tr { background:#FCE4EC; color:#B71C1C; padding:3px 10px; border-radius:6px; font-size:12px; margin:2px; display:inline-block; }

.score-big-pass { font-size: 64px; font-weight:700; color:#2E7D32; text-align:center; }
.score-big-fail { font-size: 64px; font-weight:700; color:#C62828; text-align:center; }
</style>
""", unsafe_allow_html=True)

# ─── ثوابت ────────────────────────────────────────────────────────────────
DB = "maqraa_smart.db"
ERROR_TYPES = {
    "ht": {"label": "حفظ — تنبيه",   "points": 1, "tag": "tag-ht"},
    "hr": {"label": "حفظ — رد",       "points": 2, "tag": "tag-hr"},
    "tt": {"label": "تشكيل — تنبيه", "points": 2, "tag": "tag-tt"},
    "tr": {"label": "تشكيل — رد",    "points": 4, "tag": "tag-tr"},
}
CYCLE_NAMES = ["الأولى", "الثانية", "الثالثة", "الرابعة"]
COVERAGE_OPTIONS = ["جزء واحد", "جزئين", "3 أجزاء", "5 أجزاء", "10 أجزاء", "15 جزءاً", "20 جزءاً", "25 جزءاً", "القرآن كاملاً (30 جزءاً)"]

# ─── قاعدة البيانات ────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            birth_year TEXT,
            branch TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS exams (
            id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            student_name TEXT NOT NULL,
            birth_year TEXT,
            student_branch TEXT DEFAULT '',
            teacher TEXT DEFAULT '',
            cycle_year TEXT NOT NULL,
            cycle_num INTEGER NOT NULL,
            exam_date TEXT NOT NULL,
            coverage TEXT NOT NULL,
            score INTEGER NOT NULL,
            deductions INTEGER NOT NULL,
            pass_fail INTEGER NOT NULL,
            questions TEXT NOT NULL,
            saved_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()

init_db()

# ─── المعالج الذكي للنصوص ──────────────────────────────────────────────────
def smart_parse(text):
    # تنظيف النص وتقسيمه بناءً على الأسطر غير الفارغة
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    results = []
    i = 0
    while i < len(lines):
        try:
            # التحقق من أن السطر الحالي هو الوقت (مثلاً 5:30)
            if re.match(r'\d+[:.]\d+', lines[i]):
                entry = {
                    "time": lines[i],
                    "id": lines[i+2] if i+2 < len(lines) else "",
                    "name": lines[i+3] + " " + (lines[i+4] if i+4 < len(lines) and not lines[i+4].isdigit() else ""),
                    "coverage": lines[i+6] if i+6 < len(lines) else "",
                    "birth_year": lines[i+8] if i+8 < len(lines) else "",
                    "branch": lines[i+10] if i+10 < len(lines) else ""
                }
                results.append(entry)
                i += 10 # القفزة بناءً على الترتيب المكتشف
            else:
                i += 1
        except: i += 1
    return results

# ─── دوال مساعدة من كودك الأصلي ──────────────────────────────────────────
def uid(prefix="id"):
    import random, string
    rnd = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"{prefix}_{int(datetime.now().timestamp()*1000)}_{rnd}"

def cycle_name(year, num):
    n = int(num) - 1
    return f"الدورة {CYCLE_NAMES[n]} لعام {year}" if 0 <= n < 4 else f"الدورة {num} لعام {year}"

def calc_score(questions):
    ded = sum(ERROR_TYPES[e]["points"] for q in questions for e in q.get("errors", []) if e in ERROR_TYPES)
    return {"deductions": ded, "score": 100 - ded, "pass": ded <= 20}

def fmt_date(ds):
    if not ds: return ""
    try: return datetime.strptime(str(ds), "%Y-%m-%d").strftime("%d/%m/%Y")
    except: return str(ds)

def error_tags_html(errors):
    return " ".join(f'<span class="{ERROR_TYPES[e]["tag"]}">{ERROR_TYPES[e]["label"]}</span>' for e in errors if e in ERROR_TYPES) or '<span style="color:#aaa;font-size:12px">لا أخطاء</span>'

# ─── حالة الجلسة ──────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "page": "الرئيسية", "exam_step": 1, "queue": [],
        "bulk_teacher": "", "bulk_cycle": "الأولى",
        "ex_sid": "", "ex_snm": "", "ex_sbr": "", "ex_birth": "",
        "ex_teacher": "", "ex_cy": str(datetime.now().year),
        "ex_cn": 1, "ex_dt": date.today(), "ex_co": "",
        "ex_qs": [{"pg": "", "errors": []} for _ in range(4)],
        "exam_result": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

init_state()

# ─── Header ────────────────────────────────────────────────────────────────
st.markdown('<div class="hdr"><h1>🕌 مقرأة تسميع القرآن الذكية</h1><p>نظام إدارة اللجنة والمتابعة الفورية</p></div>', unsafe_allow_html=True)

# ─── Navigation ────────────────────────────────────────────────────────────
pages = ["الرئيسية", "استيراد ذكي", "اللجنة والانتظار", "السجل", "الإحصائيات"]
nav_cols = st.columns(len(pages))
for i, p in enumerate(pages):
    if nav_cols[i].button(p, type="primary" if st.session_state.page == p else "secondary", use_container_width=True):
        st.session_state.page = p
        if p == "الرئيسية": st.session_state.exam_result = None
        st.rerun()

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════
# الرئيسية
# ══════════════════════════════════════════════════════════════════════════
if st.session_state.page == "الرئيسية":
    conn = get_db()
    exams = conn.execute("SELECT * FROM exams ORDER BY saved_at DESC").fetchall()
    total = len(exams); passed = sum(1 for e in exams if e["pass_fail"])
    rate = round(passed / total * 100) if total else 0

    c1, c2, c3 = st.columns(3)
    c1.markdown(f'<div class="metric-card"><div class="metric-num">{total}</div><div class="metric-lbl">إجمالي الاختبارات</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-card" style="border-right:4px solid #2E7D32"><div class="metric-num" style="color:#2E7D32">{passed}</div><div class="metric-lbl">ناجحة</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-card"><div class="metric-num" style="color:var(--purple)">{rate}%</div><div class="metric-lbl">نسبة النجاح</div></div>', unsafe_allow_html=True)

    st.markdown("### آخر الاختبارات اليوم")
    for e in exams[:5]:
        st.markdown(f'<div class="exam-row"><strong>{e["student_name"]}</strong> | {e["coverage"]} | الدرجة: {e["score"]}</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
# استيراد ذكي
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "استيراد ذكي":
    st.subheader("📝 سحب بيانات الطالبات من الجدول")
    with st.expander("🛠 إعدادات اللجنة", expanded=True):
        c1, c2 = st.columns(2)
        st.session_state.bulk_teacher = c1.text_input("اسم المعلمة في اللجنة", value=st.session_state.bulk_teacher)
        st.session_state.bulk_cycle = c2.selectbox("رقم الدورة", CYCLE_NAMES)
    
    raw_text = st.text_area("انسخ البيانات من الجدول وضعها هنا...", height=250)
    if st.button("تحليل البيانات وإنشاء القائمة 🚀", use_container_width=True, type="primary"):
        if raw_text:
            parsed = smart_parse(raw_text)
            if parsed:
                st.session_state.queue = parsed
                st.success(f"تم التعرف على {len(parsed)} طالبة!")
                st.session_state.page = "اللجنة والانتظار"
                st.rerun()
            else: st.error("تأكد من نسخ الجدول بشكل صحيح.")

# ══════════════════════════════════════════════════════════════════════════
# اللجنة والانتظار
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "اللجنة والانتظار":
    st.subheader("⏳ قائمة انتظار اليوم")
    if not st.session_state.queue:
        st.info("القائمة فارغة. اذهب لصفحة 'استيراد ذكي'.")
    else:
        for idx, s in enumerate(st.session_state.queue):
            col_info, col_btn = st.columns([4, 1])
            with col_info:
                st.markdown(f'<div class="waiting-card"><div><strong>{s["name"]}</strong><br><small>مواليد: {s["birth_year"]} | {s["coverage"]}</small></div><div class="badge-gold">{s["time"]}</div></div>', unsafe_allow_html=True)
            with col_btn:
                if st.button("بدء", key=f"q_{idx}"):
                    st.session_state.ex_sid = s['id']; st.session_state.ex_snm = s['name']
                    st.session_state.ex_sbr = s['branch']; st.session_state.ex_co = s['coverage']
                    st.session_state.ex_birth = s['birth_year']; st.session_state.ex_teacher = st.session_state.bulk_teacher
                    st.session_state.ex_cn = CYCLE_NAMES.index(st.session_state.bulk_cycle) + 1
                    st.session_state.exam_step = 2; st.session_state.page = "اختبار جديد"
                    st.rerun()

# ══════════════════════════════════════════════════════════════════════════
# اختبار جديد (تسجيل الأخطاء)
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "اختبار جديد":
    if st.session_state.exam_result:
        res = st.session_state.exam_result
        st.markdown(f'<div style="background:{"#E8F5E9" if res["pass"] else "#FFEBEE"}; padding:30px; border-radius:15px; text-align:center"><h1>{res["score"]}</h1><h3>{"ناجحة ✓" if res["pass"] else "راسبة ✗"}</h3></div>', unsafe_allow_html=True)
        if st.button("العودة لقائمة الانتظار"): 
            st.session_state.exam_result = None
            st.session_state.page = "اللجنة والانتظار"; st.rerun()
        st.stop()

    if st.session_state.exam_step == 2:
        st.markdown(f"### تسجيل أخطاء: {st.session_state.ex_snm}")
        res = calc_score(st.session_state.ex_qs)
        st.metric("الدرجة الحالية", res["score"], delta=f"-{res['deductions']}")

        tabs = st.tabs(["جزء 1", "جزء 2", "جزء 3", "جزء 4"])
        for i, tab in enumerate(tabs):
            with tab:
                st.session_state.ex_qs[i]["pg"] = st.text_input("الصفحة", key=f"p_{i}")
                c1, c2 = st.columns(2)
                if c1.button("⚠️ حفظ — تنبيه", key=f"ht_{i}"): st.session_state.ex_qs[i]["errors"].append("ht"); st.rerun()
                if c2.button("🟠 حفظ — رد", key=f"hr_{i}"): st.session_state.ex_qs[i]["errors"].append("hr"); st.rerun()
                if st.session_state.ex_qs[i]["errors"]:
                    st.markdown(error_tags_html(st.session_state.ex_qs[i]["errors"]), unsafe_allow_html=True)
                    if st.button("🗑 مسح", key=f"clr_{i}"): st.session_state.ex_qs[i]["errors"] = []; st.rerun()

        if st.button("💾 حفظ الاختبار النهائي", type="primary", use_container_width=True):
            conn = get_db()
            eid = uid("ex")
            conn.execute("INSERT INTO exams VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                eid, st.session_state.ex_sid, st.session_state.ex_snm, st.session_state.ex_birth,
                st.session_state.ex_sbr, st.session_state.ex_teacher, st.session_state.ex_cy,
                st.session_state.ex_cn, str(st.session_state.ex_dt), st.session_state.ex_co,
                res["score"], res["deductions"], 1 if res["pass"] else 0,
                json.dumps(st.session_state.ex_qs, ensure_ascii=False), datetime.now().isoformat()
            ))
            # حذف الطالبة من قائمة الانتظار بعد الحفظ
            st.session_state.queue = [s for s in st.session_state.queue if s['name'] != st.session_state.ex_snm]
            conn.commit(); conn.close()
            st.session_state.exam_result = {"score": res["score"], "pass": res["pass"]}
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════
# السجل والإحصائيات
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "السجل":
    conn = get_db()
    exams = conn.execute("SELECT * FROM exams ORDER BY saved_at DESC").fetchall()
    for e in exams:
        with st.expander(f"{e['student_name']} - {e['score']}"):
            st.write(f"المقرر: {e['coverage']} | التاريخ: {e['exam_date']} | المواليد: {e['birth_year']}")

elif st.session_state.page == "الإحصائيات":
    st.subheader("📊 تحليل الأداء")
    st.write("الإحصائيات تعمل بناءً على قاعدة البيانات المحدثة...")
