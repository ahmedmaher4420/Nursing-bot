import os
import random
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from Quizzes import quizzes  # ملف الكويز القديم

TOKEN = "8419066396:AAEgaf63xX_GKQSCTBQf5cy9Q9I91CnDJdo"
BASE_PATH = os.path.join(os.getcwd(), "Lectures")

app = Flask(__name__)
telegram_app = Application.builder().token(TOKEN).build()

# 🧠 كلاس إدارة جلسة المستخدم
class UserSession:
    def __init__(self):
        self.stage_stack = []
        self.subject = None
        self.stage = None
        self.lecture = None
        self.quiz = None
        self.review_list = []

# 🧩 لوحة الأزرار
def base_keyboard(extra_buttons=None, in_quiz=False):
    buttons = extra_buttons[:] if extra_buttons else []
    if in_quiz:
        buttons.append(["🏁 إنهاء الكويز"])
    else:
        buttons.append(["🏠 القائمة الرئيسية"])
    return buttons

# 🔹 جلب المواد والمحاضرات
def get_subjects():
    return sorted(list(quizzes.keys()))

def get_lectures(subject):
    subject_path = os.path.join(BASE_PATH, subject)
    if not os.path.exists(subject_path):
        return []
    return sorted([f for f in os.listdir(subject_path) if f.endswith(".pdf")])

# 🚀 بدء البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['session'] = UserSession()
    subjects = get_subjects()
    keyboard = [[s] for s in subjects]
    keyboard = base_keyboard(keyboard)
    await update.message.reply_text(
        "Welcome to Nursing Hub\nاختر المادة:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# 🧩 عرض خيارات المادة
async def show_subject_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = context.user_data['session']
    session.subject = update.message.text
    session.stage_stack.append("main")
    session.stage = "subject_options"

    keyboard = [["📄 عرض المحاضرات"], ["🧠 عرض الكويزات"]]
    keyboard = base_keyboard(keyboard)
    await update.message.reply_text(
        f"📚 اختر ما تريد في مادة *{session.subject}*:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        parse_mode="Markdown"
    )

# 🧩 عرض المحاضرات
async def show_lectures(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = context.user_data['session']
    lectures = get_lectures(session.subject)
    if not lectures:
        await update.message.reply_text("❌ لا توجد محاضرات لهذه المادة.")
        return

    session.stage_stack.append("subject_options")
    session.stage = "lectures"
    keyboard = [[lec.replace(".pdf", "")] for lec in lectures]
    keyboard = base_keyboard(keyboard)
    await update.message.reply_text(
        f"📄 اختر المحاضرة من مادة *{session.subject}*:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        parse_mode="Markdown"
    )

# 📘 عرض PDF مع رسالة جاري التحميل
async def show_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = context.user_data['session']
    selected_lecture = update.message.text
    session.lecture = selected_lecture + ".pdf"
    session.stage_stack.append("lecture_selection")

    file_path = os.path.join(BASE_PATH, session.subject, session.lecture)
    if not os.path.exists(file_path):
        await update.message.reply_text("❌ الملف غير موجود.")
        return

    # إرسال رسالة جاري التحميل
    loading_msg = await update.message.reply_text("⏳ جاري تحميل المحاضرة...")

    try:
        # إرسال الملف
        with open(file_path, "rb") as f:
            await context.bot.send_document(
                chat_id=update.message.chat_id,
                document=f,
                filename=session.lecture,
                caption=f"📘 {session.lecture}"
            )
        # حذف رسالة جاري التحميل
        await context.bot.delete_message(chat_id=update.message.chat_id, message_id=loading_msg.message_id)
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ أثناء تحميل الملف: {str(e)}")

# 🧠 عرض كل الكويزات
async def show_all_quizzes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = context.user_data['session']
    session.stage_stack.append("subject_options")
    session.stage = "quizzes"
    all_quizzes = [k for k in quizzes.get(session.subject, {})]
    if not all_quizzes:
        await update.message.reply_text("❌ لا توجد كويزات لهذه المادة.")
        return

    keyboard = [[q] for q in all_quizzes]
    keyboard = base_keyboard(keyboard)
    await update.message.reply_text(
        "🧠 اختر الكويز الذي تريد البدء به:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# 🧠 بدء الكويز
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = context.user_data['session']
    if session.stage != "quizzes":
        return  # ليس كويز، تجاهل
    quiz_name = update.message.text
    quiz_data = quizzes[session.subject][quiz_name].copy()
    random.shuffle(quiz_data)

    if session.review_list:
        quiz_data += session.review_list
        session.review_list.clear()

    session.quiz = {"name": quiz_name, "questions": quiz_data, "current_q": 0, "score": 0}
    session.stage_stack.append("quiz")
    await send_next_question(update, context)

# 🔸 إرسال السؤال التالي
async def send_next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = context.user_data['session']
    quiz_state = session.quiz
    if not quiz_state:
        return
    q_index = quiz_state["current_q"]
    questions = quiz_state["questions"]
    if q_index >= len(questions):
        await update.message.reply_text(f"✅ انتهى الكويز!\nنتيجتك: {quiz_state['score']}/{len(questions)}")
        session.quiz = None
        await go_home(update, context)
        return

    q = questions[q_index]
    keyboard = [[opt] for opt in q.get("options", [])]
    keyboard = base_keyboard(keyboard, in_quiz=True)
    await update.message.reply_text(
        f"🧩 السؤال {q_index+1} من {len(questions)}:\n{q['question']}",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ✅ التعامل مع إجابات الكويز
async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = context.user_data['session']
    quiz_state = session.quiz
    answer = update.message.text.strip()
    if answer == "🏁 إنهاء الكويز":
        await update.message.reply_text(f"⏹️ تم إنهاء الكويز.\nنتيجتك: {quiz_state['score']}/{len(quiz_state['questions'])}")
        session.quiz = None
        await go_home(update, context)
        return

    q_index = quiz_state["current_q"]
    q = quiz_state["questions"][q_index]
    if answer == q.get("answer"):
        quiz_state["score"] += 1
        await update.message.reply_text("✅ إجابة صحيحة!")
    else:
        await update.message.reply_text(f"❌ خطأ! الإجابة الصحيحة: {q.get('answer')}")
        session.review_list.append(q)

    quiz_state["current_q"] += 1
    await send_next_question(update, context)

# 🏠 العودة للقائمة الرئيسية
async def go_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['session'] = UserSession()
    subjects = get_subjects()
    keyboard = [[s] for s in subjects]
    keyboard = base_keyboard(keyboard)
    await update.message.reply_text(
        "🏠 عدت إلى القائمة الرئيسية.\nاختر المادة:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ⬅️ الرجوع خطوة واحدة
async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = context.user_data['session']
    if not session.stage_stack:
        await go_home(update, context)
        return

    last_stage = session.stage_stack.pop()
    if last_stage == "main":
        await go_home(update, context)
    elif last_stage == "subject_options":
        await show_subject_options(update, context)
    elif last_stage == "lecture_selection":
        await show_lectures(update, context)
    elif last_stage == "quiz":
        pass  # لا نرجع داخل الكويز، فقط انهاء

# 🎯 التعامل مع الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = context.user_data.setdefault('session', UserSession())
    text = update.message.text

    if session.quiz:
        await handle_quiz_answer(update, context)
        return

    if text in get_subjects():
        await show_subject_options(update, context)
    elif text == "📄 عرض المحاضرات":
        await show_lectures(update, context)
    elif text == "🧠 عرض الكويزات":
        await show_all_quizzes(update, context)
    elif text == "🏠 القائمة الرئيسية":
        await go_home(update, context)
    elif text == "⬅️ رجوع":
        await go_back(update, context)
    else:
        # التمييز بين المحاضرة والكويز حسب المرحلة
        if session.stage == "lectures":
            await show_pdf(update, context)
        elif session.stage == "quizzes":
            await start_quiz(update, context)

# 🚀 تشغيل البوت
# 🧠 Webhook endpoint
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put(update)
    return "OK", 200

if __name__ == "__main__":
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Flask server running with Webhook...")
    app.run(host="0.0.0.0", port=8080)
