import random
import re
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import keyboards as kb
from database import get_lessons, get_lesson, get_questions, save_result

router = Router()


# ─── FSM для игры ───────────────────────────────────────────────────
class Game(StatesGroup):
    choosing_lesson = State()   # выбираем урок
    playing = State()           # играем


# ─── Выбор типа игры (из main_menu → "Играть") ─────────────────────
@router.message(F.text == "🖼 Картинка → слово")
async def choose_image_word(message: Message, state: FSMContext):
    await state.update_data(q_type="image_word")
    await show_lesson_choice(message, state)


@router.message(F.text == "🇷🇺 Слово → перевод")
async def choose_word_translate(message: Message, state: FSMContext):
    await state.update_data(q_type="word_translate")
    await show_lesson_choice(message, state)


@router.message(F.text == "✏️ Фразы (ввод)")
async def choose_phrase_translate(message: Message, state: FSMContext):
    await state.update_data(q_type="phrase_translate")
    await show_lesson_choice(message, state)


async def show_lesson_choice(message: Message, state: FSMContext):
    """Показываем список уроков для выбора."""
    lessons = get_lessons()
    if not lessons:
        await message.answer(
            "📭 Пока нет загруженных уроков. Попросите преподавателя загрузить материал!",
            reply_markup=kb.main_menu(),
        )
        return

    await state.set_state(Game.choosing_lesson)
    await message.answer(
        "Выберите урок:",
        reply_markup=kb.lessons_list(lessons),
    )


# ─── Выбор урока ────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("choose_lesson:"))
async def lesson_chosen(callback: CallbackQuery, state: FSMContext):
    lesson_id = int(callback.data.split(":")[1])
    lesson = get_lesson(lesson_id)
    if not lesson:
        await callback.answer("Урок не найден.")
        return

    data = await state.get_data()
    q_type = data.get("q_type")

    # Загружаем вопросы
    questions = get_questions(lesson_id, q_type, limit=20)
    if not questions:
        await callback.message.edit_text(
            f"❌ В уроке «{lesson['title']}» нет вопросов типа «{q_type}».\n"
            "Попросите преподавателя добавить их.",
        )
        await state.clear()
        await callback.answer()
        return

    # Инициализируем состояние игры
    random.shuffle(questions)
    await state.update_data(
        lesson_id=lesson_id,
        lesson_title=lesson["title"],
        questions=[dict(q) for q in questions],
        current_index=0,
        correct_count=0,
        total_count=len(questions),
        user_id=callback.from_user.id,
    )
    await state.set_state(Game.playing)

    # Удаляем сообщение с выбором урока
    await callback.message.delete()

    # Начинаем игру
    await send_question(callback.message, state)
    await callback.answer()


# ─── Отправка вопроса ───────────────────────────────────────────────
async def send_question(message: Message, state: FSMContext):
    """Отправляет текущий вопрос пользователю."""
    data = await state.get_data()
    questions = data["questions"]
    idx = data["current_index"]

    if idx >= len(questions):
        await finish_game(message, state)
        return

    q = questions[idx]
    q_type = data["q_type"]

    question_num = idx + 1
    total = len(questions)

    if q_type == "image_word":
        await send_image_question(message, q, question_num, total, state)
    elif q_type == "word_translate":
        await send_word_question(message, q, question_num, total, state)
    elif q_type == "phrase_translate":
        await send_phrase_question(message, q, question_num, total, state)


async def send_image_question(message: Message, q: dict, num: int, total: int, state: FSMContext):
    """Показываем картинку + варианты немецких слов."""
    options = build_options(q)
    caption = (
        f"🖼 Вопрос {num}/{total}: Какое это слово?\n"
        f"Подсказка: {q['word_ru']}"
    )

    await message.answer_photo(
        photo=q["image_id"],
        caption=caption,
        reply_markup=kb.answer_options(options, q["word_de"]),
    )


async def send_word_question(message: Message, q: dict, num: int, total: int, state: FSMContext):
    """Показываем русское слово, 4 варианта немецких."""
    options = build_options(q)
    text = (
        f"🇷🇺 Вопрос {num}/{total}: Как переводится «{q['word_ru']}»?"
    )
    await message.answer(
        text,
        reply_markup=kb.answer_options(options, q["word_de"]),
    )


async def send_phrase_question(message: Message, q: dict, num: int, total: int, state: FSMContext):
    """Показываем немецкую фразу, ждём ввод перевода."""
    text = (
        f"✏️ Вопрос {num}/{total}: Переведите на русский:\n\n"
        f"🇩🇪 {q['phrase_de']}"
    )
    # Сохраняем правильный ответ во временное поле
    await state.update_data(current_correct_ru=q["phrase_ru"])
    await message.answer(text)


def build_options(q: dict) -> list[str]:
    """Собираем 4 варианта ответа: правильный + 3 неправильных."""
    correct = q["word_de"]
    wrongs = [q.get("wrong1_de", ""), q.get("wrong2_de", ""), q.get("wrong3_de", "")]
    # Фильтруем пустые и дубликаты
    wrongs = [w for w in wrongs if w and w != correct]
    # Если не хватает неправильных, добиваем
    while len(wrongs) < 3:
        wrongs.append(f"(другое)")
    # Берём только 3
    wrongs = wrongs[:3]
    options = [correct] + wrongs
    random.shuffle(options)
    return options


# ─── Обработка ответов на вопросы с вариантами (image_word, word_translate) ──
@router.callback_query(Game.playing, F.data.startswith("answer:"))
async def handle_answer(callback: CallbackQuery, state: FSMContext):
    answer = callback.data.split(":", 1)[1]
    data = await state.get_data()
    if not data:
        await callback.answer("Игра не активна.")
        return
    questions = data["questions"]
    idx = data["current_index"]
    q = questions[idx]

    correct = q["word_de"]
    is_correct = (answer == correct)

    if is_correct:
        await state.update_data(correct_count=data["correct_count"] + 1)

    # Показываем результат ответа
    if is_correct:
        feedback = f"✅ Верно! «{correct}» — {q['word_ru']}"
    else:
        feedback = f"❌ Неверно. Правильный ответ: «{correct}» — {q['word_ru']}"

    await callback.message.edit_caption(caption=feedback)

    # Следующий вопрос
    await state.update_data(current_index=idx + 1)
    await send_question(callback.message, state)
    await callback.answer()


# ─── Обработка текстовых ответов (phrase_translate) ─────────────────
@router.message(Game.playing, F.text)
async def handle_phrase_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data or data.get("q_type") != "phrase_translate":
        return

    correct_ru = data.get("current_correct_ru", "").strip().lower()
    user_answer = message.text.strip().lower()

    # Нормализация: убираем знаки препинания
    clean_user = re.sub(r'[^\w\s]', '', user_answer)
    clean_correct = re.sub(r'[^\w\s]', '', correct_ru)

    is_correct = (clean_user == clean_correct)

    if is_correct:
        await state.update_data(correct_count=data["correct_count"] + 1)
        feedback = f"✅ Верно! «{data['current_correct_ru']}»"
    else:
        feedback = f"❌ Неверно. Правильный ответ: «{correct_ru}»"

    await message.answer(feedback)

    idx = data["current_index"] + 1
    await state.update_data(current_index=idx)
    await send_question(message, state)


# ─── Финиш игры ─────────────────────────────────────────────────────
async def finish_game(message: Message, state: FSMContext):
    """Подводим итоги и показываем результат."""
    data = await state.get_data()
    if not data:
        return

    correct = data["correct_count"]
    total = data["total_count"]
    lesson_id = data["lesson_id"]
    lesson_title = data["lesson_title"]
    q_type = data["q_type"]
    user_id = data.get("user_id", message.from_user.id)

    # Сохраняем результат (один раз!)
    save_result(
        user_id=user_id,
        lesson_id=lesson_id,
        q_type=q_type,
        total=total,
        correct=correct,
    )

    pct = correct / total if total > 0 else 0
    if pct >= 0.95:
        grade = "🌟 Отлично!"
    elif pct >= 0.80:
        grade = "👍 Хорошо"
    elif pct >= 0.60:
        grade = "👌 Удовлетворительно"
    else:
        grade = "📚 Нужно повторить материал"

    type_labels = {
        "image_word": "🖼 Картинка → слово",
        "word_translate": "🇷🇺 Слово → перевод",
        "phrase_translate": "✏️ Фразы",
    }
    type_label = type_labels.get(q_type, q_type)

    result_text = (
        f"🎮 Игра завершена!\n\n"
        f"📚 Урок: {lesson_title}\n"
        f"📊 Тип: {type_label}\n"
        f"✅ Правильных: {correct} из {total}\n"
        f"🏆 Оценка: {grade}\n\n"
        f"Нажмите «Повторить» чтобы пройти ещё раз, или вернитесь в меню."
    )

    await message.answer(
        result_text,
        reply_markup=kb.result_action(lesson_id),
    )
    await state.clear()


# ─── Повторная игра ─────────────────────────────────────────────────
@router.callback_query(F.data.startswith("repeat:"))
async def repeat_game(callback: CallbackQuery, state: FSMContext):
    lesson_id = int(callback.data.split(":")[1])
    lesson = get_lesson(lesson_id)
    if not lesson:
        await callback.answer("Урок не найден.")
        return

    await callback.message.delete()
    await callback.message.answer(
        "Выберите тип заданий для этого урока:",
        reply_markup=kb.game_type_choice(),
    )
    await callback.answer()