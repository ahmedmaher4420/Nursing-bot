import os
import asyncio
import random
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from quizzes import quizzes

TOKEN = "8419066396:AAEgaf63xX_GKQSCTBQf5cy9Q9I91CnDJdo"

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
LECTURES_PATH = os.path.join(BASE_PATH, "Lectures")

user_data = {}

# ======================
# Keyboards
# ======================

def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["📚 المحاضرات", "📝 الكويزات"],
            ["⬅️ رجوع"]
        ],
        resize_keyboard=True
    )

# ======================
# Helpers
# ======================

def get_subjects():
    return list(quizzes.keys())

def get_lectures(subject):
    path = os.path.join(LECTURES_PATH, subject)
    if not os.path.exists(path):
        return []
    return sorted([f for f in os.listdir(path) if f.endswith(".pdf")])

# ======================
# Start
# ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    user_data[user_id] = {
        "state": "subjects"
    }

    subjects = get_subjects()
    keyboard = [[s] for s in subjects]

    await update.message.reply_text(
        "اختار المادة:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ======================
# Main Handler
# ======================

async def handle_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text
        user_id = update.message.from_user.id

        if user_id not in user_data:
            user_data[user_id] = {"state": "subjects"}

        state = user_data[user_id].get("state")

        # ======================
        # رجوع
        # ======================
        if text == "⬅️ رجوع":
            if state == "quiz_running":
                await update.message.reply_text("كمل الكويز الأول 😄")
                return

            await start(update, context)
            return

        # ======================
        # اختيار مادة
        # ======================
        if text in get_subjects():
            user_data[user_id]["subject"] = text
            user_data[user_id]["state"] = "main_menu"

            await update.message.reply_text(
                f"اخترت {text}",
                reply_markup=main_menu_keyboard()
            )
            return

        # ======================
        # المحاضرات
        # ======================
        if text == "📚 المحاضرات":
            subject = user_data[user_id].get("subject")

            if not subject:
                await update.message.reply_text("اختار المادة الأول")
                return

            lectures = get_lectures(subject)

            keyboard = [[l] for l in lectures]
            keyboard.append(["⬅️ رجوع"])

            user_data[user_id]["state"] = "lectures"

            await update.message.reply_text(
                "اختار المحاضرة:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return

        # ======================
        # ارسال محاضرة
        # ======================
        subject = user_data[user_id].get("subject")
        if subject:
            lectures = get_lectures(subject)

            if text in lectures:
                file_path = os.path.join(LECTURES_PATH, subject, text)

                with open(file_path, "rb") as f:
                    await context.bot.send_document(
                        chat_id=user_id,
                        document=f
                    )
                return

        # ======================
        # الكويزات
        # ======================
        if text == "📝 الكويزات":
            subject = user_data[user_id].get("subject")

            if not subject:
                await update.message.reply_text("اختار المادة الأول")
                return

            subject_quizzes = quizzes.get(subject, {})

            keyboard = [[q] for q in subject_quizzes.keys()]
            keyboard.append(["⬅️ رجوع"])

            user_data[user_id]["state"] = "quizzes"

            await update.message.reply_text(
                "اختار الكويز:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return

        # ======================
        # بدء الكويز
        # ======================
        if subject:
            subject_quizzes = quizzes.get(subject, {})

            if text in subject_quizzes:
                questions = subject_quizzes[text].copy()

                random.shuffle(questions)
                for q in questions:
                    random.shuffle(q["options"])

                user_data[user_id]["quiz"] = questions
                user_data[user_id]["index"] = 0
                user_data[user_id]["score"] = 0
                user_data[user_id]["state"] = "quiz_running"

                await send_question(update, user_id)
                return

        # ======================
        # اجابة
        # ======================
        if "quiz" in user_data[user_id]:
            q_data = user_data[user_id]

            # إنهاء الكويز
            if text == "⛔ إنهاء الكويز":
                score = q_data["score"]
                total = len(q_data["quiz"])
                percentage = int((score / total) * 100)

                await update.message.reply_text(
                    f"جدع 👏🏾 \n\n📊 Score: {score}/{total}\n🔥 Percentage: {percentage}%",
                    reply_markup=main_menu_keyboard()
                )

                del user_data[user_id]["quiz"]
                user_data[user_id]["state"] = "main_menu"
                return

            question = q_data["quiz"][q_data["index"]]
            correct = question["answer"]
            explanation = question.get("explanation")

            if text == correct:
                q_data["score"] += 1
                if explanation:
                    feedback = f"✅ صح\n\n💡 {explanation}"
                else:
                    feedback = "✅ صح"
            else:
                if explanation:
                    feedback = f"❌ غلط\n✔️ الإجابة: {correct}\n\n💡 {explanation}"
                else:
                    feedback = f"❌ غلط\n✔️ الإجابة: {correct}"

            q_data["index"] += 1

            await update.message.reply_text(feedback)
            await asyncio.sleep(1)

            if q_data["index"] < len(q_data["quiz"]):
                await send_question(update, user_id)
            else:
                score = q_data["score"]
                total = len(q_data["quiz"])
                percentage = int((score / total) * 100)

                await update.message.reply_text(
                    f"🎉 خلصت الكويز\n\n📊 Score: {score}/{total}\n🔥 Percentage: {percentage}%",
                    reply_markup=main_menu_keyboard()
                )

                del user_data[user_id]["quiz"]
                user_data[user_id]["state"] = "main_menu"

    except Exception as e:
        print(e)
        await update.message.reply_text("حصل مشكلة بسيطة.. جرب تاني")

# ======================
# سؤال
# ======================

async def send_question(update, user_id):
    q_data = user_data[user_id]
    question = q_data["quiz"][q_data["index"]]

    question_text = f"سؤال {q_data['index'] + 1} من {len(q_data['quiz'])}\n\n{question['question']}"

    keyboard = [[opt] for opt in question["options"]]
    keyboard.append(["⛔ إنهاء الكويز"])

    await update.message.reply_text(
        question_text,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ======================
# Run
# ======================

from telegram.request import HTTPXRequest

def main():
    request = HTTPXRequest(
        proxy=None,              # ❌ يمنع proxy
        connect_timeout=30,
        read_timeout=30
    )

    app = ApplicationBuilder().token(TOKEN).request(request).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all))

    print("Bot running...")
    app.run_polling()
