"""
مقرأة تسميع القرآن الكريم — Streamlit
التشغيل: streamlit run maqraa.py
"""

import streamlit as st
import sqlite3, json, os
from datetime import datetime, date

# ─── إعداد الصفحة ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="مقرأة تسميع القرآن",
    page_icon="🕌",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Cairo', sans-serif !important;
    direction: rtl;
}
h1, h2, h3 { font-family: 'Cairo', sans-serif !important; }

/* Header */
.hdr {
    background: linear-gradient(135deg, #27500A, #3B6D11);
    padding: 16px 20px;
    border-radius: 12px;
    text-align: center;
    margin-bottom: 20px;
}
.hdr h1 { color: #C0DD97; font-size: 22px; margin: 0; }
.hdr p  { color: #97C459; font-size: 13px; margin: 4px 0 0; }

/* Cards */
.metric-card {
    background: #fff;
    border-radius: 10px;
    padding: 16px;
    text-align: center;
    border: 1px solid #E0EAD0;
    box-shadow: 0 1px 4px rgba(0,0,0,.05);
}
.metric-num  { font-size: 32px; font-weight: 700; color: #3B6D11; }
.metric-lbl  { font-size: 12px; color: #888; margin-top: 4px; }

/* Exam row */
.exam-row {
    background: #fff;
    border-right: 4px solid #3B6D11;
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 8px;
    border-top: 1px solid #eee;
    border-bottom: 1px solid #eee;
    border-left: 1px solid #eee;
}
.exam-row.fail { border-right-color: #E24B4A; }

/* Badges */
.badge-pass { background:#E8F5E9; color:#2E7D32; padding:3px 10px; border-radius:20px; font-size:13px; font-weight:600; }
.badge-fail { background:#FFEBEE; color:#C62828; padding:3px 10px; border-radius:20px; font-size:13px; font-weight:600; }

/* Error tags */
.tag-ht { background:#FFF9C4; color:#F57F17; padding:2px 8px; border-radius:6px; font-size:12px; margin:2px; display:inline-block; }
.tag-hr { background:#FFF3E0; color:#BF360C; padding:2px 8px; border-radius:6px; font-size:12px; margin:2px; display:inline-block; }
.tag-tt { background:#E3F2FD; color:#1565C0; padding:2px 8px; border-radius:6px; font-size:12px; margin:2px; display:inline-block; }
.tag-tr { background:#FCE4EC; color:#B71C1C; padding:2px 8px; border-radius:6px; font-size:12px; margin:2px; display:inline-block; }

.score-big-pass { font-size: 64px; font-weight:700; color:#2E7D32; text-align:center; }
.score-big-fail { font-size: 64px; font-weight:700; color:#C62828; text-align:center; }
</style>
""", unsafe_allow_html=True)

# ─── ثوابت ────────────────────────────────────────────────────────────────
DB = "maqraa.db"

ERROR_TYPES = {
    "ht": {"label": "حفظ — تنبيه",   "points": 1, "tag": "tag-ht"},
    "hr": {"label": "حفظ — رد",       "points": 2, "tag": "tag-hr"},
    "tt": {"label": "تشكيل — تنبيه", "points": 2, "tag": "tag-tt"},
    "tr": {"label": "تشكيل — رد",    "points": 4, "tag": "tag-tr"},
}

CYCLE_NAMES = ["الأولى", "الثانية", "الثالثة", "الرابعة"]

COVERAGE_OPTIONS = [
    "جزء واحد", "جزئين", "3 أجزاء", "5 أجزاء",
    "10 أجزاء", "15 جزءاً", "20 جزءاً", "25 جزءاً",
    "القرآن كاملاً (30 جزءاً)"
]

# ─── قاعدة البيانات ────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id   TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            branch TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS teachers (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS exams (
            id              TEXT PRIMARY KEY,
            student_id      TEXT NOT NULL,
            student_name    TEXT NOT NULL,
            student_branch  TEXT DEFAULT '',
            teacher         TEXT DEFAULT '',
            cycle_year      TEXT NOT NULL,
            cycle_num       INTEGER NOT NULL,
            exam_date       TEXT NOT NULL,
            coverage        TEXT NOT NULL,
            score           INTEGER NOT NULL,
            deductions      INTEGER NOT NULL,
            pass_fail       INTEGER NOT NULL,
            questions       TEXT NOT NULL,
            saved_at        TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()

init_db()

# ─── دوال مساعدة ──────────────────────────────────────────────────────────
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

def get_students():
    return get_db().execute("SELECT * FROM students ORDER BY name").fetchall()

def get_teachers():
    return [r["name"] for r in get_db().execute("SELECT name FROM teachers ORDER BY name").fetchall()]

def get_exams(limit=None):
    q = "SELECT * FROM exams ORDER BY saved_at DESC"
    if limit: q += f" LIMIT {limit}"
    return get_db().execute(q).fetchall()

def error_tags_html(errors):
    return " ".join(
        f'<span class="{ERROR_TYPES[e]["tag"]}">{ERROR_TYPES[e]["label"]}</span>'
        for e in errors if e in ERROR_TYPES
    ) or '<span style="color:#aaa;font-size:12px">لا أخطاء</span>'

# ─── حالة الجلسة ──────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "page": "الرئيسية",
        "exam_step": 1,
        # بيانات الاختبار
        "ex_sid": "", "ex_snm": "", "ex_sbr": "",
        "ex_teacher": "", "ex_cy": str(datetime.now().year),
        "ex_cn": 1, "ex_dt": date.today(), "ex_co": "",
        "ex_qs": [{"pg": "", "errors": []} for _ in range(4)],
        "ex_cq": 0,  # السؤال الحالي
        "exam_result": None,
        # فلتر السجل
        "hist_filter": "الكل", "hist_search": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ─── Header ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hdr">
  <h1>🕌 مقرأة تسميع القرآن الكريم</h1>
  <p>نظام إدارة اختبارات التسميع</p>
</div>
""", unsafe_allow_html=True)

# ─── Navigation ────────────────────────────────────────────────────────────
pages = ["الرئيسية", "اختبار جديد", "الطالبات", "السجل", "الإحصائيات"]
icons  = ["🏠", "📝", "👩", "📋", "📊"]

cols = st.columns(len(pages))
for i, (col, pg, ic) in enumerate(zip(cols, pages, icons)):
    with col:
        if st.button(f"{ic} {pg}", key=f"nav_{pg}",
                     type="primary" if st.session_state.page == pg else "secondary",
                     use_container_width=True):
            st.session_state.page = pg
            if pg == "اختبار جديد":
                # reset exam state
                st.session_state.exam_step = 1
                st.session_state.ex_qs = [{"pg": "", "errors": []} for _ in range(4)]
                st.session_state.exam_result = None
            st.rerun()

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════
# الرئيسية
# ══════════════════════════════════════════════════════════════════════════
if st.session_state.page == "الرئيسية":
    exams = get_exams()
    total = len(exams)
    passed = sum(1 for e in exams if e["pass_fail"])
    failed = total - passed
    rate = round(passed / total * 100) if total else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-num">{total}</div><div class="metric-lbl">إجمالي الاختبارات</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="metric-num" style="color:#2E7D32">{passed}</div><div class="metric-lbl">ناجحة</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="metric-num" style="color:#C62828">{failed}</div><div class="metric-lbl">راسبة</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="metric-card"><div class="metric-num" style="color:#1565C0">{rate}%</div><div class="metric-lbl">نسبة النجاح</div></div>', unsafe_allow_html=True)

    if total:
        st.progress(rate / 100)

    st.markdown("### آخر الاختبارات")
    recent = list(exams[:6])
    if recent:
        for e in recent:
            cls = "" if e["pass_fail"] else "fail"
            badge = '<span class="badge-pass">ناجحة ✓</span>' if e["pass_fail"] else '<span class="badge-fail">راسبة ✗</span>'
            st.markdown(f"""
            <div class="exam-row {cls}">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <div>
                  <strong style="font-size:15px">{e['student_name']}</strong>
                  {'<span style="color:#aaa;font-size:12px"> | ' + e['student_branch'] + '</span>' if e['student_branch'] else ''}
                  <div style="font-size:12px;color:#888;margin-top:3px">
                    {cycle_name(e['cycle_year'], e['cycle_num'])} &bull; {fmt_date(e['exam_date'])}
                  </div>
                </div>
                <div style="text-align:center">
                  <div style="font-size:28px;font-weight:700;color:{'#2E7D32' if e['pass_fail'] else '#C62828'}">{e['score']}</div>
                  {badge}
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("لا توجد اختبارات بعد — ابدأ باختبار جديد!")

    if st.button("📝 اختبار جديد الآن", type="primary", use_container_width=True):
        st.session_state.page = "اختبار جديد"
        st.session_state.exam_step = 1
        st.session_state.ex_qs = [{"pg": "", "errors": []} for _ in range(4)]
        st.session_state.exam_result = None
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════
# اختبار جديد
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "اختبار جديد":

    # ── نتيجة محفوظة ──────────────────────────────────────────
    if st.session_state.exam_result:
        res = st.session_state.exam_result
        cls_big = "score-big-pass" if res["pass"] else "score-big-fail"
        bg_clr  = "#E8F5E9" if res["pass"] else "#FFEBEE"
        result_text = "✅ ناجحة" if res["pass"] else "❌ راسبة"

        st.markdown(f"""
        <div style="background:{bg_clr};border-radius:14px;padding:24px;text-align:center;margin-bottom:16px">
          <div class="{cls_big}">{res['score']}</div>
          <div style="font-size:22px;margin-top:6px">{result_text}</div>
          <div style="color:#666;margin-top:6px">{res['name']} &bull; خصم: {res['ded']}</div>
        </div>
        """, unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("📝 اختبار جديد", use_container_width=True, type="primary"):
                st.session_state.exam_step = 1
                st.session_state.ex_qs = [{"pg": "", "errors": []} for _ in range(4)]
                st.session_state.exam_result = None
                st.rerun()
        with c2:
            if st.button("📋 عرض السجل", use_container_width=True):
                st.session_state.page = "السجل"
                st.rerun()
        st.stop()

    step = st.session_state.exam_step

    # ── خطوة 1: بيانات أساسية ──────────────────────────────────
    if step == 1:
        st.markdown("### 📝 الخطوة 1 من 3 — بيانات الاختبار")
        students = get_students()
        stu_names = ["— طالبة جديدة —"] + [s["name"] for s in students]

        sel = st.selectbox("الطالبة", stu_names, key="stu_select")
        if sel == "— طالبة جديدة —":
            c1, c2 = st.columns(2)
            with c1: snm = st.text_input("الاسم الكامل *", key="new_snm")
            with c2: sbr = st.text_input("الفرع / المجموعة", key="new_sbr")
            sid = ""
        else:
            stu_obj = next(s for s in students if s["name"] == sel)
            snm, sbr, sid = stu_obj["name"], stu_obj["branch"], stu_obj["id"]
            st.info(f"الفرع: {sbr}" if sbr else "لا يوجد فرع مسجل")

        c1, c2, c3 = st.columns(3)
        with c1: cy = st.number_input("السنة", value=int(st.session_state.ex_cy), min_value=2020, max_value=2099, step=1)
        with c2: cn = st.selectbox("الدورة", CYCLE_NAMES, index=st.session_state.ex_cn - 1)
        with c3: dt = st.date_input("تاريخ الاختبار", value=st.session_state.ex_dt)

        co = st.selectbox("القدر المحفوظ *", ["— اختر —"] + COVERAGE_OPTIONS,
                          index=0 if not st.session_state.ex_co else
                          COVERAGE_OPTIONS.index(st.session_state.ex_co) + 1
                          if st.session_state.ex_co in COVERAGE_OPTIONS else 0)

        teachers = get_teachers()
        teacher_input = st.text_input("المُسمِّعة (اختياري)",
                                      value=st.session_state.ex_teacher,
                                      placeholder="اكتب الاسم أو اختر من القائمة")
        if teachers:
            tc_sel = st.selectbox("أو اختر من السابقات", ["—"] + teachers, key="tc_sel")
            if tc_sel != "—":
                teacher_input = tc_sel

        if st.button("التالي: تسجيل الأخطاء ←", type="primary", use_container_width=True):
            name_val = snm if sel == "— طالبة جديدة —" else sel
            if not name_val or name_val.strip() == "":
                st.error("الرجاء إدخال اسم الطالبة")
            elif co == "— اختر —":
                st.error("الرجاء اختيار القدر المحفوظ")
            else:
                st.session_state.ex_sid     = sid
                st.session_state.ex_snm     = name_val.strip()
                st.session_state.ex_sbr     = sbr if sel == "— طالبة جديدة —" else sbr
                st.session_state.ex_teacher = teacher_input
                st.session_state.ex_cy      = str(cy)
                st.session_state.ex_cn      = CYCLE_NAMES.index(cn) + 1
                st.session_state.ex_dt      = dt
                st.session_state.ex_co      = co
                st.session_state.exam_step  = 2
                st.rerun()

    # ── خطوة 2: الأخطاء ────────────────────────────────────────
    elif step == 2:
        st.markdown("### 📝 الخطوة 2 من 3 — تسجيل الأخطاء")

        # الدرجة الحية
        res = calc_score(st.session_state.ex_qs)
        badge_color = "#2E7D32" if res["pass"] else "#C62828"
        status_txt  = "ناجحة ✓" if res["pass"] else "راسبة ✗"
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("الدرجة الحالية", res["score"])
        with c2: st.metric("إجمالي الخصم", f'−{res["deductions"]}')
        with c3: st.markdown(f'<div style="padding:18px 0;text-align:center"><span style="background:{"#E8F5E9" if res["pass"] else "#FFEBEE"};color:{badge_color};padding:6px 14px;border-radius:20px;font-size:15px;font-weight:600">{status_txt}</span></div>', unsafe_allow_html=True)

        st.markdown("---")

        # علامات تبويب الأسئلة
        q_labels = []
        for i in range(4):
            ded_i = sum(ERROR_TYPES[e]["points"] for e in st.session_state.ex_qs[i]["errors"] if e in ERROR_TYPES)
            q_labels.append(f"السؤال {i+1}" + (f" (−{ded_i})" if ded_i else ""))

        tabs = st.tabs(q_labels)
        for i, tab in enumerate(tabs):
            with tab:
                st.session_state.ex_qs[i]["pg"] = st.text_input(
                    "رقم الصفحة", value=st.session_state.ex_qs[i]["pg"],
                    placeholder="اختياري", key=f"pg_{i}"
                )

                st.markdown("**نوع الخطأ:**")
                bc1, bc2 = st.columns(2)
                with bc1:
                    if st.button("⚠️ حفظ — تنبيه\n−1 نقطة", key=f"ht_{i}", use_container_width=True):
                        st.session_state.ex_qs[i]["errors"].append("ht"); st.rerun()
                    if st.button("🔵 تشكيل — تنبيه\n−2 نقطة", key=f"tt_{i}", use_container_width=True):
                        st.session_state.ex_qs[i]["errors"].append("tt"); st.rerun()
                with bc2:
                    if st.button("🟠 حفظ — رد\n−2 نقطة", key=f"hr_{i}", use_container_width=True):
                        st.session_state.ex_qs[i]["errors"].append("hr"); st.rerun()
                    if st.button("🔴 تشكيل — رد\n−4 نقاط", key=f"tr_{i}", use_container_width=True):
                        st.session_state.ex_qs[i]["errors"].append("tr"); st.rerun()

                errs = st.session_state.ex_qs[i]["errors"]
                if errs:
                    st.markdown("**الأخطاء المسجلة:**")
                    err_html = " ".join(
                        f'<span class="{ERROR_TYPES[e]["tag"]}">{ERROR_TYPES[e]["label"]} (−{ERROR_TYPES[e]["points"]})</span>'
                        for e in errs
                    )
                    st.markdown(err_html, unsafe_allow_html=True)
                    if st.button("🗑 مسح آخر خطأ", key=f"undo_{i}"):
                        st.session_state.ex_qs[i]["errors"].pop(); st.rerun()
                    if st.button("🗑🗑 مسح كل أخطاء هذا السؤال", key=f"clr_{i}"):
                        st.session_state.ex_qs[i]["errors"] = []; st.rerun()
                else:
                    st.success("لا أخطاء في هذا السؤال ✓")

        st.markdown("---")
        c1, c2 = st.columns([1, 2])
        with c1:
            if st.button("← رجوع", use_container_width=True):
                st.session_state.exam_step = 1; st.rerun()
        with c2:
            if st.button("مراجعة وحفظ ←", type="primary", use_container_width=True):
                st.session_state.exam_step = 3; st.rerun()

    # ── خطوة 3: مراجعة وحفظ ───────────────────────────────────
    elif step == 3:
        st.markdown("### 📝 الخطوة 3 من 3 — مراجعة وحفظ")

        res = calc_score(st.session_state.ex_qs)
        bg  = "#E8F5E9" if res["pass"] else "#FFEBEE"
        sc  = str(res["score"])
        cl  = "#2E7D32" if res["pass"] else "#C62828"

        st.markdown(f"""
        <div style="background:{bg};border-radius:12px;padding:16px;margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <div>
              <div style="font-size:17px;font-weight:700">{st.session_state.ex_snm}</div>
              {'<div style="font-size:13px;color:#888">' + st.session_state.ex_sbr + '</div>' if st.session_state.ex_sbr else ''}
              <div style="font-size:13px;color:#666;margin-top:4px">
                {cycle_name(st.session_state.ex_cy, st.session_state.ex_cn)}
              </div>
              <div style="font-size:13px;color:#666">
                {fmt_date(str(st.session_state.ex_dt))} &bull; {st.session_state.ex_co}
              </div>
              {'<div style="font-size:13px;color:#888">المُسمِّعة: ' + st.session_state.ex_teacher + '</div>' if st.session_state.ex_teacher else ''}
            </div>
            <div style="text-align:center">
              <div style="font-size:52px;font-weight:700;color:{cl}">{sc}</div>
              <span class="{'badge-pass' if res['pass'] else 'badge-fail'}">{'ناجحة ✓' if res['pass'] else 'راسبة ✗'}</span>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # تفاصيل الأجزاء
        st.markdown("**تفصيل الأجزاء:**")
        for i, q in enumerate(st.session_state.ex_qs):
            pg_txt = f" — ص{q['pg']}" if q["pg"] else ""
            tags = error_tags_html(q["errors"])
            st.markdown(f"""
            <div style="background:#fff;border-radius:8px;padding:10px 14px;margin-bottom:6px;
                        border:1px solid #eee;border-right:3px solid {'#E24B4A' if q['errors'] else '#3B6D11'}">
              <strong>السؤال {i+1}{pg_txt}</strong><br>
              <div style="margin-top:6px">{tags}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        c1, c2 = st.columns([1, 2])
        with c1:
            if st.button("← تعديل", use_container_width=True):
                st.session_state.exam_step = 2; st.rerun()
        with c2:
            if st.button("💾 حفظ الاختبار", type="primary", use_container_width=True):
                conn = get_db()
                sid = st.session_state.ex_sid

                # إضافة طالبة جديدة إذا لزم
                if not sid:
                    exist = conn.execute("SELECT id FROM students WHERE name=?",
                                         (st.session_state.ex_snm,)).fetchone()
                    if exist:
                        sid = exist["id"]
                    else:
                        sid = uid("stu")
                        conn.execute("INSERT INTO students VALUES (?,?,?,?)",
                                     (sid, st.session_state.ex_snm,
                                      st.session_state.ex_sbr, datetime.now().isoformat()))

                # حفظ المُسمِّعة
                if st.session_state.ex_teacher:
                    conn.execute("INSERT OR IGNORE INTO teachers (name) VALUES (?)",
                                 (st.session_state.ex_teacher,))

                eid = uid("ex")
                conn.execute("""INSERT INTO exams VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    eid, sid,
                    st.session_state.ex_snm, st.session_state.ex_sbr,
                    st.session_state.ex_teacher,
                    st.session_state.ex_cy, st.session_state.ex_cn,
                    str(st.session_state.ex_dt),
                    st.session_state.ex_co,
                    res["score"], res["deductions"],
                    1 if res["pass"] else 0,
                    json.dumps(st.session_state.ex_qs, ensure_ascii=False),
                    datetime.now().isoformat()
                ))
                conn.commit()
                conn.close()

                st.session_state.exam_result = {
                    "score": res["score"], "ded": res["deductions"],
                    "pass": res["pass"], "name": st.session_state.ex_snm
                }
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════
# الطالبات
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "الطالبات":
    st.markdown("### 👩 إدارة الطالبات")

    with st.expander("➕ إضافة طالبة جديدة", expanded=True):
        c1, c2 = st.columns(2)
        with c1: new_name   = st.text_input("الاسم *", key="add_stu_name")
        with c2: new_branch = st.text_input("الفرع / المجموعة", key="add_stu_branch")
        if st.button("إضافة", type="primary", use_container_width=True):
            if not new_name.strip():
                st.error("الاسم مطلوب")
            else:
                conn = get_db()
                existing = conn.execute("SELECT id FROM students WHERE name=?",
                                        (new_name.strip(),)).fetchone()
                if existing:
                    st.error("هذا الاسم موجود مسبقاً")
                else:
                    conn.execute("INSERT INTO students VALUES (?,?,?,?)",
                                 (uid("stu"), new_name.strip(), new_branch.strip(),
                                  datetime.now().isoformat()))
                    conn.commit()
                    st.success(f"تمت إضافة {new_name}")
                    st.rerun()

    st.markdown("---")
    students = get_students()
    conn = get_db()

    if not students:
        st.info("لا توجد طالبات مسجلات بعد")
    else:
        st.markdown(f"**إجمالي الطالبات: {len(students)}**")
        for s in students:
            cnt  = conn.execute("SELECT COUNT(*) as c FROM exams WHERE student_id=?",
                                (s["id"],)).fetchone()["c"]
            last = conn.execute("SELECT pass_fail FROM exams WHERE student_id=? "
                                "ORDER BY saved_at DESC LIMIT 1", (s["id"],)).fetchone()

            badge = ""
            if last:
                badge = '<span class="badge-pass">آخر: ناجحة</span>' if last["pass_fail"] \
                        else '<span class="badge-fail">آخر: راسبة</span>'

            st.markdown(f"""
            <div class="exam-row">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <div>
                  <strong>{s['name']}</strong>
                  {'<span style="color:#aaa;font-size:12px"> | ' + s['branch'] + '</span>' if s['branch'] else ''}
                  <div style="font-size:12px;color:#888;margin-top:3px">{cnt} اختبار {badge}</div>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button(f"🗑 حذف {s['name']}", key=f"del_stu_{s['id']}"):
                conn.execute("DELETE FROM students WHERE id=?", (s["id"],))
                conn.execute("DELETE FROM exams WHERE student_id=?", (s["id"],))
                conn.commit()
                st.success(f"تم حذف {s['name']}")
                st.rerun()

    conn.close()

# ══════════════════════════════════════════════════════════════════════════
# السجل
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "السجل":
    st.markdown("### 📋 سجل الاختبارات")

    c1, c2 = st.columns([3, 1])
    with c1:
        search = st.text_input("🔍 بحث باسم الطالبة", value=st.session_state.hist_search,
                               placeholder="اكتب للبحث...")
    with c2:
        filt = st.selectbox("الحالة", ["الكل", "ناجحات فقط", "راسبات فقط"],
                            index=["الكل", "ناجحات فقط", "راسبات فقط"].index(
                                st.session_state.hist_filter))

    st.session_state.hist_search = search
    st.session_state.hist_filter = filt

    exams = get_exams()
    if search:
        exams = [e for e in exams if search in e["student_name"]]
    if filt == "ناجحات فقط":
        exams = [e for e in exams if e["pass_fail"]]
    elif filt == "راسبات فقط":
        exams = [e for e in exams if not e["pass_fail"]]

    st.markdown(f"**النتائج: {len(exams)} اختبار**")

    if not exams:
        st.info("لا توجد اختبارات تطابق المعايير")
    else:
        for e in exams:
            cls   = "" if e["pass_fail"] else "fail"
            badge = '<span class="badge-pass">ناجحة ✓</span>' if e["pass_fail"] \
                    else '<span class="badge-fail">راسبة ✗</span>'

            with st.expander(
                f"{'✅' if e['pass_fail'] else '❌'} {e['student_name']} — "
                f"الدرجة: {e['score']} — {fmt_date(e['exam_date'])}"
            ):
                qs = json.loads(e["questions"])
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.markdown(f"""
                    **الدورة:** {cycle_name(e['cycle_year'], e['cycle_num'])}  
                    **التاريخ:** {fmt_date(e['exam_date'])}  
                    **القدر:** {e['coverage']}  
                    {'**المُسمِّعة:** ' + e['teacher'] if e['teacher'] else ''}  
                    {'**الفرع:** ' + e['student_branch'] if e['student_branch'] else ''}
                    """)
                with c2:
                    sc_cl = "#2E7D32" if e["pass_fail"] else "#C62828"
                    st.markdown(f"""
                    <div style="text-align:center;padding:10px">
                      <div style="font-size:42px;font-weight:700;color:{sc_cl}">{e['score']}</div>
                      {badge}
                      <div style="font-size:12px;color:#888;margin-top:4px">خصم: {e['deductions']}</div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("**تفصيل الأجزاء:**")
                for i, q in enumerate(qs):
                    pg_t = f" — ص{q['pg']}" if q.get("pg") else ""
                    tags = error_tags_html(q.get("errors", []))
                    st.markdown(f"""
                    <div style="background:#fafafa;padding:8px 12px;border-radius:6px;
                                margin-bottom:5px;border-right:3px solid {'#E24B4A' if q.get('errors') else '#3B6D11'}">
                      <strong>السؤال {i+1}{pg_t}:</strong> {tags}
                    </div>
                    """, unsafe_allow_html=True)

                if st.button(f"🗑 حذف هذا الاختبار", key=f"del_ex_{e['id']}",
                             type="secondary"):
                    conn = get_db()
                    conn.execute("DELETE FROM exams WHERE id=?", (e["id"],))
                    conn.commit()
                    conn.close()
                    st.success("تم الحذف")
                    st.rerun()

# ══════════════════════════════════════════════════════════════════════════
# الإحصائيات
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "الإحصائيات":
    st.markdown("### 📊 الإحصائيات")

    exams = get_exams()
    total = len(exams)

    if not total:
        st.info("لا توجد بيانات بعد — أضف اختبارات أولاً")
        st.stop()

    passed = sum(1 for e in exams if e["pass_fail"])
    failed = total - passed
    rate   = round(passed / total * 100)
    avg_sc = round(sum(e["score"] for e in exams) / total)

    # ── الأعداد العامة ───────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("الاختبارات", total)
    c2.metric("ناجحة", passed, delta=f"{rate}%")
    c3.metric("راسبة", failed)
    c4.metric("متوسط الدرجات", avg_sc)

    st.progress(rate / 100)
    st.caption(f"نسبة النجاح: {rate}%")

    # ── توزيع أنواع الأخطاء ─────────────────────────
    st.markdown("---")
    st.markdown("#### توزيع أنواع الأخطاء")

    err_counts = {k: 0 for k in ERROR_TYPES}
    for e in exams:
        for q in json.loads(e["questions"]):
            for err in q.get("errors", []):
                if err in err_counts:
                    err_counts[err] += 1

    total_errs = sum(err_counts.values())
    if total_errs:
        for k, v in sorted(err_counts.items(), key=lambda x: -x[1]):
            pct = round(v / total_errs * 100) if total_errs else 0
            st.markdown(
                f'<span class="{ERROR_TYPES[k]["tag"]}">{ERROR_TYPES[k]["label"]}</span> '
                f'— **{v}** ({pct}%)', unsafe_allow_html=True
            )
            st.progress(pct / 100)
    else:
        st.info("لا توجد أخطاء مسجلة")

    # ── إحصائيات لكل طالبة ───────────────────────────
    st.markdown("---")
    st.markdown("#### إحصائيات الطالبات")

    stu_map = {}
    for e in exams:
        sid = e["student_id"]
        if sid not in stu_map:
            stu_map[sid] = {"name": e["student_name"], "total": 0, "passed": 0, "scores": []}
        stu_map[sid]["total"]  += 1
        stu_map[sid]["passed"] += int(e["pass_fail"])
        stu_map[sid]["scores"].append(e["score"])

    rows = []
    for s in stu_map.values():
        rows.append({
            "الطالبة":     s["name"],
            "الاختبارات":  s["total"],
            "ناجحة":       s["passed"],
            "نسبة النجاح": f'{round(s["passed"]/s["total"]*100)}%',
            "متوسط الدرجات": round(sum(s["scores"]) / len(s["scores"])),
        })

    rows.sort(key=lambda r: -r["الاختبارات"])

    # عرض الجدول بدون مكتبة خارجية
    st.markdown("""
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <thead>
        <tr style="background:#F0F6E8">
          <th style="padding:8px 10px;text-align:right;border-bottom:2px solid #C8D8B8">الطالبة</th>
          <th style="padding:8px;text-align:center;border-bottom:2px solid #C8D8B8">الاختبارات</th>
          <th style="padding:8px;text-align:center;border-bottom:2px solid #C8D8B8">ناجحة</th>
          <th style="padding:8px;text-align:center;border-bottom:2px solid #C8D8B8">نسبة النجاح</th>
          <th style="padding:8px;text-align:center;border-bottom:2px solid #C8D8B8">متوسط الدرجات</th>
        </tr>
      </thead>
      <tbody>
    """ + "".join(f"""
        <tr style="border-bottom:1px solid #F0F0F0">
          <td style="padding:8px 10px;font-weight:600">{r['الطالبة']}</td>
          <td style="padding:8px;text-align:center">{r['الاختبارات']}</td>
          <td style="padding:8px;text-align:center">{r['ناجحة']}</td>
          <td style="padding:8px;text-align:center">
            <span class="{'badge-pass' if int(r['نسبة النجاح'][:-1])>=80 else 'badge-fail'}">{r['نسبة النجاح']}</span>
          </td>
          <td style="padding:8px;text-align:center;font-weight:700;color:{'#2E7D32' if r['متوسط الدرجات']>=80 else '#C62828'}">{r['متوسط الدرجات']}</td>
        </tr>
    """ for r in rows) + """
      </tbody>
    </table>
    """, unsafe_allow_html=True)
