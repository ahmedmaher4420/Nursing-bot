import os
import random
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from Quizzes import quizzes  # استيراد الكويزات من الملف الجديد

BASE_PATH = os.path.join(os.getcwd(), "Lectures")

# 🧠 كلاس لإدارة الحالة
class UserSession:
    def __init__(self):
        self.subject = None
        self.lecture = None
        self.stage = "main"
        self.quiz = None
        self.review_list = []
        self.history = []
        self.all_quizzes = []
        self.selected_quiz_info = None

sessions = {}

# 🧩 لوحة الأزرار العامة
def base_keyboard(extra_buttons=None, in_quiz=False, show_back=False):
    base = []
    if extra_buttons:
        base += extra_buttons

    if show_back:
        base.append(["⬅️ رجوع"])

    if in_quiz:
        base.append(["🏁 إنهاء الكويز"])
    else:
        base.append(["🏠 القائمة الرئيسية"])

    return base

# 🔹 جلب المواد
def get_subjects():
    return sorted(list(quizzes.keys()))

# 🔹 جلب المحاضرات
def get_lectures(subject):
    subject_path = os.path.join(BASE_PATH, subject)
    if not os.path.exists(subject_path):
        return []
    return [f for f in os.listdir(subject_path) if f.endswith(".pdf")]

# 🔹 جمع كل الكويزات في المادة
def get_all_quizzes(subject):
    all_quizzes = []
    if subject not in quizzes:
        return all_quizzes
    for key, value in quizzes[subject].items():
        all_quizzes.append({"lecture": None, "quiz_name": key})
    return all_quizzes

# 🚀 بدء البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    sessions[chat_id] = UserSession()

    subjects = get_subjects()
    if not subjects:
        await update.message.reply_text("❌ لا توجد مواد حالياً.")
        return

    keyboard = [[subject] for subject in subjects]
    keyboard = base_keyboard(keyboard)

    await update.message.reply_text(
        "Welcome To Nursing Hub",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# 🧩 عرض خيارات المادة
async def show_subject_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    subject = update.message.text
    session = sessions[chat_id]
    session.subject = subject
    session.stage = "subject_options"
    session.history.append("main")

    keyboard = [
        ["📄 عرض المحاضرات"],
        ["🧠 عرض الكويزات"]
    ]
    keyboard = base_keyboard(keyboard, show_back=(len(session.history) >= 1))

    await update.message.reply_text(
        f"📚 اختر ما تريد في مادة *{subject}*:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        parse_mode="Markdown"
    )

# 🧩 عرض المحاضرات
async def show_lectures(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    session = sessions[chat_id]
    subject = session.subject
    lectures = get_lectures(subject)

    if not lectures:
        await update.message.reply_text("❌ لا توجد محاضرات لهذه المادة.")
        return

    session.stage = "lecture_selection"
    session.history.append("subject_options")

    keyboard = [[lec.replace(".pdf", "")] for lec in lectures]
    keyboard = base_keyboard(keyboard, show_back=(len(session.history) >= 1))

    await update.message.reply_text(
        f"📄 اختر المحاضرة من مادة *{subject}*:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        parse_mode="Markdown"
    )

# 🎯 خيارات المحاضرة
async def lecture_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    session = sessions[chat_id]
    lecture_name = update.message.text
    subject = session.subject

    if not subject:
        await update.message.reply_text("⚠️ حدث خطأ، تم إعادتك إلى القائمة الرئيسية.")
        sessions[chat_id] = UserSession()
        await go_home(update, context)
        return

    subject_path = os.path.join(BASE_PATH, subject)
    found_lecture = None
    for f in os.listdir(subject_path):
        if f.startswith(lecture_name):
            found_lecture = f
            break

    if not found_lecture:
        await update.message.reply_text("❌ لم يتم العثور على هذه المحاضرة.")
        return

    session.lecture = found_lecture
    session.stage = "lecture_options"
    session.history.append("lecture_selection")

    keyboard = [["📖 عرض المحاضرة"]]
    keyboard = base_keyboard(keyboard, show_back=(len(session.history) >= 1))

    await update.message.reply_text(
        f"🎯 اختر ما تريد في *{lecture_name}* من مادة *{subject}*:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        parse_mode="Markdown"
    )

# 📘 عرض PDF - نسخة محسنة لتجنب التوقف
async def show_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    session = sessions.get(chat_id)
    if not session or not session.lecture:
        await update.message.reply_text("⚠️ اختر المحاضرة أولاً.")
        return

    subject = session.subject
    lecture_file = session.lecture
    file_path = os.path.join(BASE_PATH, subject, lecture_file)

    if not os.path.exists(file_path):
        await update.message.reply_text("❌ الملف غير موجود.")
        return

    try:
        with open(file_path, "rb") as pdf_file:
            await update.message.reply_document(
                document=pdf_file,
                filename=os.path.basename(file_path),
                caption=f"📘 {lecture_file}"
            )
    except Exception as e:
        await update.message.reply_text(f"⚠️ حدث خطأ أثناء فتح الملف:\n{e}")

# 🧠 بدء الكويز
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE, quiz_name):
    chat_id = update.message.chat_id
    session = sessions[chat_id]
    subject = session.subject
    lecture = None

    if session.stage == "all_quizzes" and session.selected_quiz_info:
        lecture = session.selected_quiz_info.get("lecture", None)
    elif session.lecture:
        lecture = session.lecture.replace(".pdf", "")

    if lecture and subject in quizzes and lecture in quizzes[subject]:
        quiz_data = quizzes[subject][lecture][quiz_name].copy()
    else:
        quiz_data = quizzes[subject][quiz_name].copy()

    random.shuffle(quiz_data)

    if session.review_list:
        quiz_data += session.review_list
        session.review_list.clear()

    session.quiz = {
        "name": quiz_name,
        "questions": quiz_data,
        "current_q": 0,
        "score": 0
    }
    session.stage = "quiz"
    session.history.append("all_quizzes" if session.stage == "all_quizzes" else "lecture_options")

    await send_next_question(update, context)

# 🔸 إرسال السؤال التالي
async def send_next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    session = sessions[chat_id]
    quiz_state = session.quiz
    q_index = quiz_state["current_q"]
    questions = quiz_state["questions"]

    if q_index >= len(questions):
        score = quiz_state["score"]
        total = len(questions)
        percentage = round((score / total) * 100, 1)

        await update.message.reply_text(
            f"✅ انتهيت من الكويز!\n\nنتيجتك: {score}/{total} ({percentage}%)"
        )
        session.quiz = None
        await go_home(update, context)
        return

    q = questions[q_index]
    keyboard = [[opt] for opt in q["options"]] if q.get("options") else []
    keyboard = base_keyboard(keyboard, in_quiz=True)

    await update.message.reply_text(
        f"🧩 السؤال {q_index + 1} من {len(questions)}:\n\n{q['question']}",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ✅ التعامل مع إجابات الكويز
async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    session = sessions[chat_id]
    quiz_state = session.quiz
    answer = update.message.text.strip()

    if answer == "🏁 إنهاء الكويز":
        score = quiz_state["score"]
        total = len(quiz_state["questions"])
        percentage = round((score / total) * 100, 1)
        await update.message.reply_text(f"⏹️ تم إنهاء الكويز.\nنتيجتك: {score}/{total} ({percentage}%)")
        session.quiz = None
        await go_home(update, context)
        return

    q_index = quiz_state["current_q"]
    q = quiz_state["questions"][q_index]

    if answer == q.get("answer"):
        quiz_state["score"] += 1
        await update.message.reply_text("✅ إجابة صحيحة!")
    else:
        await update.message.reply_text(f"❌ خطأ! الإجابة الصحيحة هي: {q.get('answer','غير محدد')}")
        session.review_list.append(q)

    quiz_state["current_q"] += 1
    await send_next_question(update, context)

# 🏠 القائمة الرئيسية
async def go_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    sessions[chat_id] = UserSession()

    subjects = get_subjects()
    keyboard = [[subject] for subject in subjects]
    keyboard = base_keyboard(keyboard)

    await update.message.reply_text(
        "🏠 عدت إلى القائمة الرئيسية.\nاختر المادة:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ⬅️ رجوع خطوة واحدة
async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    session = sessions[chat_id]
    if len(session.history) < 1:
        await go_home(update, context)
        return

    previous_stage = session.history.pop()
    if previous_stage == "main":
        await go_home(update, context)
    elif previous_stage == "subject_options":
        await show_subject_options(update, context)
    elif previous_stage == "lecture_selection":
        await show_lectures(update, context)
    elif previous_stage == "lecture_options":
        await lecture_options(update, context)
    elif previous_stage == "all_quizzes":
        await show_all_quizzes(update, context)

# 🧠 عرض كل الكويزات في المادة
async def show_all_quizzes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    session = sessions[chat_id]
    subject = session.subject

    all_quizzes = get_all_quizzes(subject)
    if not all_quizzes:
        await update.message.reply_text("❌ لا توجد كويزات لهذه المادة.")
        return

    session.all_quizzes = all_quizzes
    session.stage = "all_quizzes"
    session.history.append("subject_options")

    keyboard = [[q["quiz_name"]] for q in all_quizzes]
    keyboard = base_keyboard(keyboard, show_back=(len(session.history) >= 1))

    await update.message.reply_text(
        f"🧠 اختر الكويز الذي تريد البدء به:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# 🧠 بدء الكويز من قائمة كل الكويزات
async def start_quiz_from_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    session = sessions[chat_id]
    selected_quiz = update.message.text.strip()

    quiz_info = next(
        (q for q in session.all_quizzes if q["quiz_name"].strip().lower() == selected_quiz.lower()),
        None
    )

    if not quiz_info:
        await update.message.reply_text("❌ حدث خطأ، حاول مرة أخرى.")
        return

    session.selected_quiz_info = quiz_info
    await start_quiz(update, context, quiz_info["quiz_name"])

# 🎯 التعامل مع جميع الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id
    session = sessions.get(chat_id)

    if not session:
        sessions[chat_id] = UserSession()
        session = sessions[chat_id]

    if session.quiz:
        await handle_quiz_answer(update, context)
        return

    if text in get_subjects():
        await show_subject_options(update, context)
    elif text == "📄 عرض المحاضرات":
        await show_lectures(update, context)
    elif text == "🧠 عرض الكويزات":
        await show_all_quizzes(update, context)
    elif text == "📖 عرض المحاضرة":
        await show_pdf(update, context)
    elif text == "⬅️ رجوع":
        await go_back(update, context)
    elif text == "🏠 القائمة الرئيسية":
        await go_home(update, context)
    else:
        if session.stage == "all_quizzes":
            await start_quiz_from_all(update, context)
        else:
            await lecture_options(update, context)

# 🚀 تشغيل البوت
def main():
    TOKEN = "8419066396:AAEgaf63xX_GKQSCTBQf5cy9Q9I91CnDJdo"
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Nursing Hub bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
