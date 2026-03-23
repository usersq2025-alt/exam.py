import streamlit as st
import sqlite3
import json
import os
import re
import pandas as pd
from datetime import datetime, date

# ─── 1. إعدادات الصفحة ────────────────────────────────────────────────────
st.set_page_config(
    page_title="مقرأة تسميع القرآن الكريم",
    page_icon="🕌",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ─── 2. الثوابت الأساسية (يجب أن تسبق أي دالة تستخدمها) ──────────────────────
# وضعناها هنا في الأعلى ليراها البرنامج قبل أن يبدأ بالعمل
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

DB_NAME = "maqraa_smart.db"

# ─── 3. التنسيق الجمالي (CSS) ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Cairo', sans-serif !important; direction: rtl; text-align: right; }
.hdr { background: linear-gradient(135deg, #4B0082, #6A0DAD); padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 25px; border-bottom: 5px solid #D4AF37; }
.hdr h1 { color: #D4AF37; font-size: 26px; margin: 0; }
.hdr p  { color: #E6E6FA; font-size: 14px; }
.metric-card { background: #fff; border-radius: 12px; padding: 15px; text-align: center; border: 1px solid #eee; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
.metric-num  { font-size: 32px; font-weight: 700; color: #4B0082; }
.exam-row { background: #fff; border-right: 5px solid #4B0082; border-radius: 10px; padding: 15px; margin-bottom: 10px; border: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }
.badge-pass { background:#E8F5E9; color:#2E7D32; padding:4px 12px; border-radius:20px; font-size:13px; font-weight:600; }
.badge-fail { background:#FFEBEE; color:#C62828; padding:4px 12px; border-radius:20px; font-size:13px; font-weight:600; }
.tag-ht { background:#FFF9C4; color:#F57F17; padding:3px 8px; border-radius:6px; font-size:12px; margin:2px; display:inline-block; border: 1px solid #FBC02D; }
.tag-hr { background:#FFF3E0; color:#BF360C; padding:3px 8px; border-radius:6px; font-size:12px; margin:2px; display:inline-block; border: 1px solid #FF9800; }
.tag-tt { background:#E3F2FD; color:#1565C0; padding:3px 8px; border-radius:6px; font-size:12px; margin:2px; display:inline-block; border: 1px solid #2196F3; }
.tag-tr { background:#FCE4EC; color:#B71C1C; padding:3px 8px; border-radius:6px; font-size:12px; margin:2px; display:inline-block; border: 1px solid #F06292; }
</style>
""", unsafe_allow_html=True)
# ─── 4. الدوال المساعدة (Helpers) ─────────────────────────────────────────

def error_tags_html(errors):
    """تحويل قائمة الأخطاء إلى أوسمة ملونة (تعريفها هنا يمنع خطأ NameError)"""
    if not errors:
        return '<span style="color:#aaa;font-size:12px">لا أخطاء</span>'
    html_list = []
    for e in errors:
        if e in ERROR_TYPES:
            tag = ERROR_TYPES[e]["tag"]
            lbl = ERROR_TYPES[e]["label"]
            html_list.append(f'<span class="{tag}">{lbl}</span>')
    return " ".join(html_list)

def fmt_date(d_str):
    """تحويل التاريخ لصيغة مقروءة"""
    if not d_str: return ""
    try: return datetime.strptime(str(d_str), "%Y-%m-%d").strftime("%d/%m/%Y")
    except: return str(d_str)

def get_db_connection():
    """الاتصال بقاعدة البيانات"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def get_exams(limit=None):
    """دالة جلب الاختبارات (حل مشكلة NameError get_exams)"""
    query = "SELECT * FROM exams ORDER BY saved_at DESC"
    if limit: query += f" LIMIT {limit}"
    with get_db_connection() as conn:
        return conn.execute(query).fetchall()

def fetch_all_students():
    """جلب كافة الطالبات"""
    with get_db_connection() as conn:
        return conn.execute("SELECT * FROM students ORDER BY name").fetchall()
    # ─── 5. تهيئة قاعدة البيانات عند بدء التشغيل ──────────────────────────────

def init_db():
    """إنشاء الجداول وتحديثها لدعم حقل المواليد"""
    conn = get_db_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            branch TEXT DEFAULT '',
            birth_year TEXT,
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
            student_branch TEXT DEFAULT '',
            birth_year TEXT,
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
    # محاولة إضافة عمود المواليد للجداول القديمة إن لم يكن موجوداً
    try: conn.execute("ALTER TABLE students ADD COLUMN birth_year TEXT")
    except: pass
    try: conn.execute("ALTER TABLE exams ADD COLUMN birth_year TEXT")
    except: pass
    conn.commit()
    conn.close()

# تشغيل التهيئة فوراً
init_db()

# ─── 6. المعالج الذكي للبيانات المنسوخة (Parser) ──────────────────────────

def parse_bulk_text(raw_text):
    """تحليل النص المنسوخ من الجداول (7.00 م 120671 سنا محمد...)"""
    lines = raw_text.strip().split('\n')
    extracted = []
    for line in lines:
        if not line.strip(): continue
        # التقسيم بناءً على علامات التبويب أو المسافات الكبيرة
        parts = [p.strip() for p in re.split(r'\t| {2,}', line) if p.strip()]
        if len(parts) >= 8:
            extracted.append({
                "time": parts[0],
                "id": parts[2],
                "name": parts[3],
                "coverage": parts[4],
                "country": parts[5],
                "birth_year": parts[6],
                "teacher_ref": parts[-1]
            })
    return extracted
    
# ─── 3. إعداد قاعدة البيانات (SQLite) ──────────────────────────────────────
DB_NAME = "maqraa_smart.db"

def get_db_connection():
    """إنشاء اتصال بقاعدة البيانات مع تفعيل الوصول عبر أسماء الأعمدة"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn
    # ─── دالة جلب الاختبارات (الحل للمشكلة) ──────────────────────────────────────
def get_exams(limit=None):
    """
    جلب الاختبارات من قاعدة البيانات. 
    إذا تم تحديد limit يجلب عدداً معيناً، وإذا لم يحدد يجلب الكل.
    """
    query = "SELECT * FROM exams ORDER BY saved_at DESC"
    if limit:
        query += f" LIMIT {limit}"
    
    with get_db_connection() as conn:
        return conn.execute(query).fetchall()

# ─── دالة تحويل التاريخ للعرض (Helper Function) ─────────────────────────────
def fmt_date(ds):
    """تحويل صيغة التاريخ من قاعدة البيانات إلى صيغة مقروءة (يوم/شهر/سنة)"""
    if not ds: return ""
    try: 
        return datetime.strptime(str(ds), "%Y-%m-%d").strftime("%d/%m/%Y")
    except: 
        return str(ds)

# ─── دالة عرض أوسمة الأخطاء (UI Helper) ─────────────────────────────────────
def error_tags_html(errors):
    """تحويل قائمة الأخطاء المسجلة إلى كود HTML ليظهر بشكل أوسمة ملونة"""
    return " ".join(
        f'<span class="{ERROR_TYPES[e]["tag"]}">{ERROR_TYPES[e]["label"]}</span>'
        for e in errors if e in ERROR_TYPES
    ) or '<span style="color:#aaa;font-size:12px">لا أخطاء</span>'

def init_db():
    """إنشاء الجداول الأساسية وتحديثها إذا كانت موجودة مسبقاً"""
    conn = get_db_connection()
    # جدول الطالبات: أضفنا birth_year (المواليد)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            branch TEXT DEFAULT '',
            birth_year TEXT,
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
            student_branch TEXT DEFAULT '',
            birth_year TEXT,
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
    
    # التأكد من تحديث الجداول القديمة في حال وجود ملف قاعدة بيانات سابق
    try:
        conn.execute("ALTER TABLE students ADD COLUMN birth_year TEXT")
    except sqlite3.OperationalError:
        pass  # العمود موجود بالفعل
        
    try:
        conn.execute("ALTER TABLE exams ADD COLUMN birth_year TEXT")
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    conn.close()

# تشغيل تهيئة القاعدة عند بدء التطبيق
init_db()

# ─── 4. دوال جلب البيانات المساعدة ──────────────────────────────────────────
def fetch_all_students():
    """جلب قائمة جميع الطالبات مرتبة أبجدياً"""
    with get_db_connection() as conn:
        return conn.execute("SELECT * FROM students ORDER BY name").fetchall()

def fetch_all_teachers():
    """جلب أسماء المعلمات اللواتي تم تسجيلهن مسبقاً"""
    with get_db_connection() as conn:
        return [row["name"] for row in conn.execute("SELECT name FROM teachers ORDER BY name").fetchall()]

def fetch_recent_exams(limit=10):
    """جلب آخر الاختبارات المسجلة لعرضها في الصفحة الرئيسية"""
    with get_db_connection() as conn:
        return conn.execute("SELECT * FROM exams ORDER BY saved_at DESC LIMIT ?", (limit,)).fetchall()

# ─── 5. دوال الهوية والعمليات الحسابية ──────────────────────────────────────
def generate_unique_id(prefix="id"):
    """توليد معرف فريد لكل طالبة أو اختبار"""
    import random, string
    timestamp = int(datetime.now().timestamp() * 1000)
    random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"{prefix}_{timestamp}_{random_str}"

def calculate_exam_results(questions_list):
    """
    حساب الدرجة النهائية بناءً على مصفوفة الأسئلة والأخطاء.
    الأوزان: حفظ تنبيه (-1)، حفظ رد (-2)، تشكيل تنبيه (-2)، تشكيل رد (-4).
    """
    error_weights = {"ht": 1, "hr": 2, "tt": 2, "tr": 4}
    total_deductions = 0
    
    for q in questions_list:
        for error_key in q.get("errors", []):
            total_deductions += error_weights.get(error_key, 0)
            
    score = 100 - total_deductions
    is_passed = 1 if total_deductions <= 20 else 0
    
    return {
        "deductions": total_deductions,
        "score": max(0, score), # لضمان عدم نزول الدرجة تحت الصفر
        "pass": is_passed
    }
    # ─── 6. المعالج الذكي للنصوص (Smart Parser) ──────────────────────────────────
def parse_bulk_text(raw_text):
    """
    تحليل النص المنسوخ من الجداول.
    يتعامل مع التقسيم بواسطة Tab أو المسافات المتعددة (2 أو أكثر).
    التنسيق المتوقع للسطر: [الوقت] [م/ص] [المعرف] [الاسم] [المقرر] [البلد] [المواليد] ...
    """
    lines = raw_text.strip().split('\n')
    extracted_students = []
    
    for line in lines:
        if not line.strip():
            continue
            
        # التقسيم بناءً على علامة التبويب (Tab) أو المسافات المتعددة لضمان دقة فصل الأعمدة
        parts = [p.strip() for p in re.split(r'\t| {2,}', line) if p.strip()]
        
        # التأكد من وجود الحد الأدنى من البيانات (7 أعمدة على الأقل)
        if len(parts) >= 7:
            try:
                # محاولة تحديد مكان سنة الميلاد (غالباً تكون رقماً مكوناً من 4 خانات)
                birth_year = ""
                for p in parts:
                    if p.isdigit() and len(p) == 4 and int(p) > 1940:
                        birth_year = p
                        break
                
                extracted_students.append({
                    "time": parts[0],        # العمود الأول: الوقت
                    "id": parts[2],          # العمود الثالث: المعرف (تخطي م/ص)
                    "name": parts[3],        # العمود الرابع: الاسم
                    "coverage": parts[4],    # العمود الخامس: المقرر
                    "country": parts[5],     # العمود السادس: البلد
                    "birth_year": birth_year if birth_year else parts[6], # سنة الميلاد
                    "original_line": line    # للرجوع إليها عند الحاجة
                })
            except Exception as e:
                continue # تخطي الأسطر التي لا تطابق التنسيق
                
    return extracted_students

# ─── 7. تهيئة حالة الجلسة (Session State) ──────────────────────────────────
def initialize_session_state():
    """
    إعداد المتغيرات التي تحفظ حالة التطبيق أثناء التنقل.
    هذا يضمن بقاء قائمة الانتظار والبيانات المدخلة حتى لو تغيرت الصفحة.
    """
    if "page" not in st.session_state:
        st.session_state.page = "الرئيسية"
        
    if "exam_step" not in st.session_state:
        st.session_state.exam_step = 1
        
    if "queue" not in st.session_state:
        st.session_state.queue = []  # قائمة الانتظار الذكية (الـ 12 طالبة)
        
    if "bulk_teacher" not in st.session_state:
        st.session_state.bulk_teacher = ""
        
    if "bulk_cycle" not in st.session_state:
        st.session_state.bulk_cycle = "الأولى"
        
    # بيانات الاختبار الحالي (Current Exam Context)
    exam_defaults = {
        "ex_sid": "", "ex_snm": "", "ex_sbr": "", "ex_birth": "",
        "ex_teacher": "", "ex_cy": str(datetime.now().year),
        "ex_cn": 1, "ex_dt": date.today(), "ex_co": "",
        "ex_qs": [{"pg": "", "errors": []} for _ in range(4)], # 4 أسئلة كما في ملفك
        "exam_result": None,
        "hist_filter": "الكل", "hist_search": ""
    }
    
    for key, val in exam_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

# تشغيل التهيئة
initialize_session_state()
# ─── 7. إدارة حالة الجلسة (ذاكرة البرنامج) ────────────────────────────────

def initialize_state():
    """تجهيز المتغيرات التي تحفظ البيانات أثناء التنقل بين الصفحات"""
    defaults = {
        "page": "الرئيسية",
        "exam_step": 1,
        "queue": [],
        "bulk_teacher": "",
        "bulk_cycle": "الأولى",
        "ex_sid": "", "ex_snm": "", "ex_sbr": "", "ex_birth": "",
        "ex_teacher": "", "ex_cy": str(datetime.now().year),
        "ex_cn": 1, "ex_dt": date.today(), "ex_co": "",
        "ex_qs": [{"pg": "", "errors": []} for _ in range(4)],
        "exam_result": None,
        "hist_filter": "الكل", "hist_search": "",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

initialize_state()

# ─── 8. الهيدر ونظام القوائم (Navigation) ──────────────────────────────────

st.markdown("""
<div class="hdr">
  <h1>🕌 مقرأة تسميع القرآن الذكية</h1>
  <p>نظام اللجنة الذكي والمتابعة الفورية لعام 2026</p>
</div>
""", unsafe_allow_html=True)

# أزرار التنقل العلوية
pages_list = ["الرئيسية", "استيراد ذكي", "اللجنة والانتظار", "الطالبات", "السجل", "الإحصائيات"]
icons_list  = ["🏠", "📥", "⏳", "👩", "📋", "📊"]

nav_cols = st.columns(len(pages_list))
for i, (col, pg, ic) in enumerate(zip(nav_cols, pages_list, icons_list)):
    with col:
        if st.button(f"{ic}\n{pg}", key=f"nav_{pg}",
                     type="primary" if st.session_state.page == pg else "secondary",
                     use_container_width=True):
            st.session_state.page = pg
            if pg == "الرئيسية": st.session_state.exam_result = None
            st.rerun()

st.markdown("---")
# ─── 8. الهيدر والقائمة الجانبية ──────────────────────────────────────────
st.markdown("""
<div class="hdr">
  <h1>🕌 مقرأة تسميع القرآن الذكية</h1>
  <p>نظام إدارة اللجنة والمتابعة الفورية لعام 2026</p>
</div>
""", unsafe_allow_html=True)
# ─── 9. نظام التنقل (Navigation System) ────────────────────────────────────
# تعتمد هذه القائمة على الأزرار العلوية لسهولة الوصول من الهاتف أو الكمبيوتر
pages_list = ["الرئيسية", "استيراد ذكي", "اللجنة والانتظار", "الطالبات", "السجل", "الإحصائيات"]
icons_list  = ["🏠", "📥", "⏳", "👩", "📋", "📊"]

nav_cols = st.columns(len(pages_list))
for i, (col, pg, ic) in enumerate(zip(nav_cols, pages_list, icons_list)):
    with col:
        # زر التنقل مع تمييز الصفحة النشطة باللون الأساسي (الأرجواني)
        if st.button(f"{ic}\n{pg}", key=f"nav_{pg}", 
                     type="primary" if st.session_state.page == pg else "secondary",
                     use_container_width=True):
            st.session_state.page = pg
            # إعادة ضبط حالة الاختبار عند التنقل لضمان عدم التداخل
            if pg == "الرئيسية":
                st.session_state.exam_result = None
            st.rerun()

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════
# صفحة الاستيراد الذكي (Smart Import Page)
# ══════════════════════════════════════════════════════════════════════════
if st.session_state.page == "استيراد ذكي":
    st.subheader("📥 استيراد بيانات الطالبات من الجدول")
    st.write("قم بنسخ الصفوف من جدول التسميع (مثل Excel أو PDF) ولصقها هنا مباشرة.")
    
    # إعدادات المجموعة (تطبق على الـ 12 طالبة معاً لتوفير الوقت)
    with st.expander("🛠 إعدادات اللجنة والدورة الحالية", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.session_state.bulk_teacher = st.text_input(
                "اسم المعلمة (عضو اللجنة)", 
                value=st.session_state.bulk_teacher,
                placeholder="مثال: رامة.ن"
            )
        with c2:
            st.session_state.bulk_cycle = st.selectbox(
                "رقم الدورة الحالية", 
                ["الأولى", "الثانية", "الثالثة", "الرابعة"],
                index=["الأولى", "الثانية", "الثالثة", "الرابعة"].index(st.session_state.bulk_cycle)
            )
    
    # منطقة اللصق (Input Area)
    raw_input_data = st.text_area(
        "الصق صفوف الجدول هنا...", 
        height=250, 
        placeholder="7.00	م	120671	سنا محمد رضوان جعفو	21-22	سوريا	2008..."
    )
    
    if st.button("معالجة البيانات وتجهيز القائمة 🚀", type="primary", use_container_width=True):
        if raw_input_data.strip():
            # استدعاء المحلل الذكي من المرحلة 3
            parsed_results = parse_bulk_text(raw_input_data)
            
            if parsed_results:
                st.session_state.queue = parsed_results
                st.success(f"تم التعرف على {len(parsed_results)} طالبة بنجاح! يمكنك الآن الانتقال لصفحة الانتظار.")
                # الانتقال التلقائي لصفحة المتابعة
                st.session_state.page = "اللجنة والانتظار"
                st.rerun()
            else:
                st.error("عذراً، لم نتمكن من تحليل النص. تأكد من نسخ الصفوف كاملة من الجدول.")
        else:
            st.warning("الرجاء لصق البيانات أولاً.")

# ══════════════════════════════════════════════════════════════════════════
# صفحة اللجنة والانتظار (Waiting List & Monitoring)
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "اللجنة والانتظار":
    st.subheader("⏳ قائمة متابعة سير اختبارات اليوم")
    
    if not st.session_state.queue:
        st.info("قائمة الانتظار فارغة حالياً. اذهب لصفحة 'استيراد ذكي' لإضافة طالبات.")
    else:
        # عرض معلومات اللجنة المثبتة
        st.markdown(f"""
        <div style="background:#F3E5F5; padding:10px; border-radius:10px; margin-bottom:20px; border-right:4px solid #4B0082;">
            <strong>المعلمة:</strong> {st.session_state.bulk_teacher if st.session_state.bulk_teacher else 'لم تحدد'} | 
            <strong>الدورة:</strong> {st.session_state.bulk_cycle} | 
            <strong>التاريخ:</strong> {date.today().strftime('%d/%m/%Y')}
        </div>
        """, unsafe_allow_html=True)
        
        # عرض الطالبات كبطاقات (Cards)
        for idx, student in enumerate(st.session_state.queue):
            with st.container():
                col_info, col_btn = st.columns([4, 1.2])
                
                with col_info:
                    st.markdown(f"""
                    <div class="exam-row">
                        <div>
                            <strong style="color:#4B0082; font-size:18px;">{student['name']}</strong><br>
                            <span style="font-size:13px; color:#666;">
                                ID: {student['id']} | مواليد: {student['birth_year']} | المقرر: {student['coverage']}
                            </span>
                        </div>
                        <div style="text-align:right;">
                            <span style="background:#D4AF37; color:white; padding:2px 8px; border-radius:5px; font-size:12px;">
                                {student['time']}
                            </span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_btn:
                    # زر بدء التسميع لكل طالبة
                    if st.button("بدء التسميع 📝", key=f"start_{idx}_{student['id']}", use_container_width=True):
                        # 1. نقل بيانات الطالبة لـ Session State الخاص بالاختبار
                        st.session_state.ex_sid = student['id']
                        st.session_state.ex_snm = student['name']
                        st.session_state.ex_co = student['coverage']
                        st.session_state.ex_birth = student['birth_year']
                        st.session_state.ex_sbr = student.get('country', '') # استخدام البلد كفرع مؤقت
                        
                        # 2. نقل بيانات اللجنة
                        st.session_state.ex_teacher = st.session_state.bulk_teacher
                        st.session_state.ex_cn = ["الأولى", "الثانية", "الثالثة", "الرابعة"].index(st.session_state.bulk_cycle) + 1
                        st.session_state.ex_dt = date.today()
                        
                        # 3. تصفير مصفوفة الأسئلة لبدء اختبار جديد
                        st.session_state.ex_qs = [{"pg": "", "errors": []} for _ in range(4)]
                        
                        # 4. الانتقال لصفحة تسجيل الأخطاء (Step 2 مباشرة)
                        st.session_state.exam_step = 2
                        st.session_state.page = "اختبار جديد"
                        st.rerun()
                        # ══════════════════════════════════════════════════════════════════════════
# صفحة اختبار جديد (New Exam Page)
# ══════════════════════════════════════════════════════════════════════════
if st.session_state.page == "اختبار جديد":

    # ── 1. عرض النتيجة النهائية (بعد الحفظ) ──────────────────────
    if st.session_state.exam_result:
        res = st.session_state.exam_result
        cls_big = "score-big-pass" if res["pass"] else "score-big-fail"
        bg_clr  = "#E8F5E9" if res["pass"] else "#FFEBEE"
        result_text = "✅ ناجحة" if res["pass"] else "❌ راسبة"

        st.markdown(f"""
        <div style="background:{bg_clr}; border-radius:15px; padding:30px; text-align:center; margin-bottom:20px; border: 1px solid #ddd;">
          <div class="{cls_big}">{res['score']}</div>
          <div style="font-size:24px; font-weight:700; margin-top:10px;">{result_text}</div>
          <div style="color:#666; margin-top:10px;">الطالبة: {res['name']} | إجمالي الخصم: {res['ded']}</div>
        </div>
        """, unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("⏳ العودة لقائمة الانتظار", use_container_width=True, type="primary"):
                st.session_state.page = "اللجنة والانتظار"
                st.session_state.exam_result = None
                st.rerun()
        with c2:
            if st.button("📋 عرض السجل", use_container_width=True):
                st.session_state.page = "السجل"
                st.rerun()
        st.stop()

    step = st.session_state.exam_step

    # ── 2. الخطوة 1: البيانات الأساسية (تعبئة تلقائية) ──────────
    if step == 1:
        st.markdown("### 📝 الخطوة 1 من 3 — بيانات الاختبار")
        # في حال أردت إدخال طالبة يدوياً خارج القائمة الذكية
        students_list = fetch_all_students()
        stu_names = ["— طالبة جديدة —"] + [s["name"] for s in students_list]

        sel_student = st.selectbox("اختر الطالبة", stu_names, key="manual_stu_select")
        
        if sel_student == "— طالبة جديدة —":
            c1, c2 = st.columns(2)
            snm = c1.text_input("الاسم الكامل *", key="man_snm")
            sbir = c2.text_input("سنة الميلاد", key="man_birth")
            sbr = st.text_input("الفرع / المجموعة", key="man_branch")
            sid = ""
        else:
            stu_obj = next(s for s in students_list if s["name"] == sel_student)
            snm, sbr, sid, sbir = stu_obj["name"], stu_obj["branch"], stu_obj["id"], stu_obj["birth_year"]
            st.info(f"البيانات المسجلة: فرع {sbr} | مواليد {sbir}")

        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        cy = c1.number_input("السنة", value=int(st.session_state.ex_cy), min_value=2020, max_value=2099)
        cn = c2.selectbox("الدورة", CYCLE_NAMES, index=st.session_state.ex_cn - 1)
        dt = c3.date_input("تاريخ الاختبار", value=st.session_state.ex_dt)

        co = st.selectbox("القدر المحفوظ *", ["— اختر —"] + COVERAGE_OPTIONS)

        if st.button("التالي: تسجيل الأخطاء ←", type="primary", use_container_width=True):
            if not snm or co == "— اختر —":
                st.error("الرجاء إكمال البيانات الأساسية")
            else:
                st.session_state.ex_sid, st.session_state.ex_snm = sid, snm
                st.session_state.ex_birth, st.session_state.ex_co = sbir, co
                st.session_state.ex_cn = CYCLE_NAMES.index(cn) + 1
                st.session_state.exam_step = 2
                st.rerun()

    # ── 3. الخطوة 2: تسجيل الأخطاء (Logic) ──────────────────────
    elif step == 2:
        st.markdown(f"### 📝 تسجيل أخطاء الطالبة: <span style='color:#4B0082'>{st.session_state.ex_snm}</span>", unsafe_allow_html=True)
        
        # حساب الدرجة الحية (Live Score) باستخدام المعادلة:
        # $$Score = 100 - \sum (Points_{errors})$$
        res = calculate_exam_results(st.session_state.ex_qs)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("الدرجة الحالية", res["score"])
        c2.metric("إجمالي الخصم", f"-{res['deductions']}")
        status_color = "#2E7D32" if res["pass"] else "#C62828"
        c3.markdown(f"<div style='text-align:center; padding-top:10px'><span class='badge-pass' style='background:{'#E8F5E9' if res['pass'] else '#FFEBEE'}; color:{status_color}'>{'ناجحة ✓' if res['pass'] else 'راسبة ✗'}</span></div>", unsafe_allow_html=True)

        st.markdown("---")
        
        # تبويبات الأسئلة الأربعة كما في ملفك الأصلي
        tabs = st.tabs([f"السؤال {i+1}" for i in range(4)])
        for i, tab in enumerate(tabs):
            with tab:
                st.session_state.ex_qs[i]["pg"] = st.text_input(f"رقم الصفحة (السؤال {i+1})", value=st.session_state.ex_qs[i]["pg"], key=f"pg_input_{i}")
                
                st.write("**نوع الخطأ:**")
                bt1, bt2 = st.columns(2)
                # استخدام الأوزان الأصلية: HT=1, HR=2, TT=2, TR=4
                if bt1.button("⚠️ حفظ — تنبيه (−1)", key=f"btn_ht_{i}", use_container_width=True):
                    st.session_state.ex_qs[i]["errors"].append("ht"); st.rerun()
                if bt1.button("🔵 تشكيل — تنبيه (−2)", key=f"btn_tt_{i}", use_container_width=True):
                    st.session_state.ex_qs[i]["errors"].append("tt"); st.rerun()
                if bt2.button("🟠 حفظ — رد (−2)", key=f"btn_hr_{i}", use_container_width=True):
                    st.session_state.ex_qs[i]["errors"].append("hr"); st.rerun()
                if bt2.button("🔴 تشكيل — رد (−4)", key=f"btn_tr_{i}", use_container_width=True):
                    st.session_state.ex_qs[i]["errors"].append("tr"); st.rerun()

                # عرض الأخطاء المسجلة في هذا الجزء
                current_errors = st.session_state.ex_qs[i]["errors"]
                if current_errors:
                    st.markdown(error_tags_html(current_errors), unsafe_allow_html=True)
                    if st.button(f"🗑 مسح أخطاء السؤال {i+1}", key=f"clr_q_{i}"):
                        st.session_state.ex_qs[i]["errors"] = []; st.rerun()
                else:
                    st.success("لا توجد أخطاء مسجلة لهذا السؤال.")

        st.markdown("---")
        bc1, bc2 = st.columns([1, 2])
        if bc1.button("← رجوع للبيانات", use_container_width=True): 
            st.session_state.exam_step = 1; st.rerun()
        if bc2.button("مراجعة النتيجة وحفظ الاختبار ←", type="primary", use_container_width=True):
            st.session_state.exam_step = 3; st.rerun()

    # ── 4. الخطوة 3: المراجعة النهائية والحفظ ──────────────────
    elif step == 3:
        st.markdown("### 📝 المراجعة النهائية قبل الحفظ")
        res = calculate_exam_results(st.session_state.ex_qs)
        
        st.markdown(f"""
        <div style="background:#fff; border-radius:12px; padding:20px; border:1px solid #D4AF37; border-right: 8px solid #4B0082;">
            <table style="width:100%">
                <tr><td><strong>اسم الطالبة:</strong></td><td>{st.session_state.ex_snm}</td></tr>
                <tr><td><strong>المقرر:</strong></td><td>{st.session_state.ex_co}</td></tr>
                <tr><td><strong>المواليد:</strong></td><td>{st.session_state.ex_birth}</td></tr>
                <tr><td><strong>المعلمة:</strong></td><td>{st.session_state.ex_teacher}</td></tr>
                <tr><td><strong>النتيجة النهائية:</strong></td><td><span style="color:{status_color}; font-size:20px; font-weight:bold;">{res['score']}</span></td></tr>
            </table>
        </div>
        """, unsafe_allow_html=True)

        if st.button("💾 تأكيد وحفظ الاختبار في السجل", type="primary", use_container_width=True):
            conn = get_db_connection()
            # 1. تحديث أو إضافة الطالبة في جدول الطالبات
            sid = st.session_state.ex_sid
            if not sid:
                sid = generate_unique_id("stu")
                conn.execute("INSERT INTO students (id, name, branch, birth_year, created_at) VALUES (?,?,?,?,?)",
                             (sid, st.session_state.ex_snm, st.session_state.ex_sbr, st.session_state.ex_birth, datetime.now().isoformat()))
            
            # 2. حفظ المُسمّعة في جدول المعلمات (إذا لم تكن موجودة)
            if st.session_state.ex_teacher:
                conn.execute("INSERT OR IGNORE INTO teachers (name) VALUES (?)", (st.session_state.ex_teacher,))

            # 3. حفظ الاختبار النهائي
            eid = generate_unique_id("ex")
            conn.execute("INSERT INTO exams VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                eid, sid, st.session_state.ex_snm, st.session_state.ex_sbr, st.session_state.ex_birth,
                st.session_state.ex_teacher, st.session_state.ex_cy, st.session_state.ex_cn,
                str(st.session_state.ex_dt), st.session_state.ex_co, res["score"], res["deductions"],
                res["pass"], json.dumps(st.session_state.ex_qs, ensure_ascii=False), datetime.now().isoformat()
            ))
            conn.commit(); conn.close()

            # 4. إزالة الطالبة من قائمة الانتظار (Queue) لضمان عدم تكرارها
            st.session_state.queue = [s for s in st.session_state.queue if s['name'] != st.session_state.ex_snm]
            
            # 5. عرض النتيجة النهائية
            st.session_state.exam_result = {"score": res["score"], "ded": res["deductions"], "pass": res["pass"], "name": st.session_state.ex_snm}
            st.rerun()
        # ══════════════════════════════════════════════════════════════════════════
# صفحة الطالبات (Students Management)
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "الطالبات":
    st.markdown("### 👩 إدارة قاعدة بيانات الطالبات")

    # إضافة طالبة جديدة يدوياً
    with st.expander("➕ إضافة طالبة جديدة إلى النظام", expanded=False):
        c1, c2 = st.columns(2)
        new_name = c1.text_input("الاسم الكامل *", key="add_name")
        new_birth = c2.text_input("سنة الميلاد", key="add_birth", placeholder="مثال: 1995")
        new_branch = st.text_input("الفرع / المجموعة", key="add_branch")
        
        if st.button("حفظ بيانات الطالبة", type="primary", use_container_width=True):
            if not new_name.strip():
                st.error("الاسم مطلوب")
            else:
                conn = get_db_connection()
                # التحقق من عدم تكرار الاسم
                existing = conn.execute("SELECT id FROM students WHERE name=?", (new_name.strip(),)).fetchone()
                if existing:
                    st.warning("هذه الطالبة مسجلة مسبقاً في النظام.")
                else:
                    conn.execute("INSERT INTO students VALUES (?,?,?,?,?)",
                                 (generate_unique_id("stu"), new_name.strip(), new_branch.strip(), 
                                  new_birth.strip(), datetime.now().isoformat()))
                    conn.commit()
                    st.success(f"تمت إضافة {new_name} بنجاح!")
                conn.close()
                st.rerun()

    st.markdown("---")
    # عرض قائمة الطالبات
    students = fetch_all_students()
    if not students:
        st.info("لا توجد طالبات مسجلات حالياً.")
    else:
        st.markdown(f"**إجمالي الطالبات المسجلات: {len(students)}**")
        for s in students:
            with st.container():
                st.markdown(f"""
                <div class="exam-row">
                    <div>
                        <strong>{s['name']}</strong> | <span style="color:#666">مواليد: {s['birth_year']}</span><br>
                        <small>الفرع: {s['branch'] if s['branch'] else 'غير محدد'}</small>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                # زر لحذف الطالبة (اختياري)
                if st.button(f"🗑 حذف ملف {s['name']}", key=f"del_stu_{s['id']}"):
                    conn = get_db_connection()
                    conn.execute("DELETE FROM students WHERE id=?", (s["id"],))
                    conn.execute("DELETE FROM exams WHERE student_id=?", (s["id"],)) # حذف سجلاتها أيضاً
                    conn.commit(); conn.close()
                    st.rerun()

# ══════════════════════════════════════════════════════════════════════════
# صفحة السجل (Exam Records)
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "السجل":
    st.markdown("### 📋 سجل الاختبارات التفصيلي")

    # أدوات البحث والفلترة
    c1, c2 = st.columns([3, 1])
    search_query = c1.text_input("🔍 بحث باسم الطالبة", value=st.session_state.hist_search)
    filter_status = c2.selectbox("الحالة", ["الكل", "ناجحات فقط", "راسبات فقط"])
    
    st.session_state.hist_search = search_query
    
    # جلب البيانات وتطبيق الفلاتر
    exams = get_exams() # جلب كافة الاختبارات من القاعدة
    if search_query:
        exams = [e for e in exams if search_query in e["student_name"]]
    
    if filter_status == "ناجحات فقط":
        exams = [e for e in exams if e["pass_fail"]]
    elif filter_status == "راسبات فقط":
        exams = [e for e in exams if not e["pass_fail"]]

    if not exams:
        st.warning("لا توجد نتائج تطابق بحثك.")
    else:
        for e in exams:
            status_icon = "✅" if e["pass_fail"] else "❌"
            with st.expander(f"{status_icon} {e['student_name']} — الدرجة: {e['score']} — تاريخ: {fmt_date(e['exam_date'])}"):
                # تفاصيل الاختبار
                col_a, col_b = st.columns(2)
                with col_a:
                    st.write(f"**المقرر:** {e['coverage']}")
                    st.write(f"**الدورة:** {cycle_name(e['cycle_year'], e['cycle_num'])}")
                    st.write(f"**المواليد:** {e['birth_year']}")
                with col_b:
                    st.write(f"**المُسمّعة:** {e['teacher']}")
                    st.write(f"**الخصم:** {e['deductions']} نقطة")
                    st.write(f"**توقيت الحفظ:** {e['saved_at'][:16]}")

                # عرض الأخطاء بالتفصيل (JSON) كما في ملفك الأصلي
                st.markdown("**تفصيل الأسئلة والأخطاء:**")
                qs_data = json.loads(e["questions"])
                for i, q in enumerate(qs_data):
                    pg_info = f" (ص {q['pg']})" if q.get("pg") else ""
                    errors_html = error_tags_html(q.get("errors", []))
                    st.markdown(f"**س {i+1}{pg_info}:** {errors_html}", unsafe_allow_html=True)
                
                if st.button("🗑 حذف هذا الاختبار", key=f"del_ex_{e['id']}"):
                    conn = get_db_connection()
                    conn.execute("DELETE FROM exams WHERE id=?", (e["id"],))
                    conn.commit(); conn.close()
                    st.rerun()

# ══════════════════════════════════════════════════════════════════════════
# صفحة الإحصائيات (Advanced Statistics)
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "الإحصائيات":
    st.markdown("### 📊 لوحة البيانات والإحصائيات")

    exams = get_exams()
    if not exams:
        st.info("لا توجد بيانات كافية لاستخراج الإحصائيات.")
    else:
        total = len(exams)
        passed = sum(1 for e in exams if e["pass_fail"])
        avg_score = sum(e["score"] for e in exams) / total
        
        # 1. الأعداد العامة
        c1, c2, c3 = st.columns(3)
        c1.metric("إجمالي الاختبارات", total)
        c2.metric("نسبة النجاح", f"{round(passed/total*100)}%")
        c3.metric("متوسط الدرجات", f"{round(avg_score, 1)}")

        # 2. تحليل الأخطاء (توزيع أنواع الأخطاء)
        st.markdown("---")
        st.subheader("⚠️ توزيع أنواع الأخطاء")
        err_counts = {"ht": 0, "hr": 0, "tt": 0, "tr": 0}
        for e in exams:
            qs = json.loads(e["questions"])
            for q in qs:
                for err in q.get("errors", []):
                    if err in err_counts: err_counts[err] += 1
        
        # عرض التقدم لكل نوع خطأ
        for k, v in err_counts.items():
            label = ERROR_TYPES[k]["label"]
            st.write(f"{label}: {v}")
            st.progress(min(v/max(sum(err_counts.values()), 1), 1.0))

        # 3. جدول ترتيب أداء الطالبات
        st.markdown("---")
        st.subheader("🏆 سجل أداء الطالبات")
        # منطق تجميع البيانات لكل طالبة
        stu_stats = {}
        for e in exams:
            name = e["student_name"]
            if name not in stu_stats: stu_stats[name] = {"exams": 0, "passed": 0, "avg": 0}
            stu_stats[name]["exams"] += 1
            stu_stats[name]["passed"] += 1 if e["pass_fail"] else 0
            stu_stats[name]["avg"] += e["score"]
        
        # تحويلها لجدول
        report_data = []
        for name, data in stu_stats.items():
            report_data.append({
                "الطالبة": name,
                "الاختبارات": data["exams"],
                "النجاح": f"{round(data['passed']/data['exams']*100)}%",
                "المتوسط": round(data["avg"]/data["exams"], 1)
            })
        st.table(pd.DataFrame(report_data).sort_values(by="المتوسط", ascending=False))

# ══════════════════════════════════════════════════════════════════════════
# الصفحة الرئيسية (الترحيب والملخص)
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "الرئيسية":
    st.info("مرحباً بك في نظام المقرأة الذكي. ابدأ باستيراد جدول الطالبات من صفحة 'استيراد ذكي' لتنظيم لجنة اليوم.")
    st.markdown("---")
    st.write("آخر الاختبارات المسجلة اليوم:")
    recent = fetch_recent_exams(5)
    for r in recent:
        st.markdown(f"- **{r['student_name']}**: حصلت على {r['score']} في مقرر {r['coverage']}")
        
