import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import keyboards as kb
import config
from database import create_lesson, add_question, count_questions

router = Router()


# ─── FSM для загрузки урока ─────────────────────────────────────────
class UploadLesson(StatesGroup):
    # 1. Ждём название (от /new_lesson)
    waiting_for_title = State()
    # 2. Выбираем тип вопроса для добавления
    choosing_type = State()
    # 3. Ждём вопрос
    waiting_for_question = State()


# ─── /new_lesson — создать урок (только админ) ──────────────────────
@router.message(Command("new_lesson"))
async def cmd_new_lesson(message: Message, state: FSMContext):
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("⛔ Нет доступа.")
        return

    # Извлекаем название из команды
    text = message.text.removeprefix("/new_lesson").strip()
    if not text:
        await message.answer(
            "Используйте: `/new_lesson Название урока`\n"
            "Например: `/new_lesson Урок 5 — Семья`",
            reply_markup=kb.cancel_kb(),
        )
        return

    lesson_id = create_lesson(text)
    await state.update_data(lesson_id=lesson_id, lesson_title=text)
    await state.set_state(UploadLesson.choosing_type)

    await message.answer(
        f"✅ Урок «{text}» создан (id: {lesson_id}).\n\n"
        "Теперь добавляйте вопросы. Выберите тип:",
        reply_markup=kb.game_type_choice(),
    )


# ─── Отмена ─────────────────────────────────────────────────────────
@router.message(F.text == "❌ Отмена")
async def cancel_upload(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Загрузка отменена.", reply_markup=kb.main_menu())


# ─── Выбор типа вопроса для добавления ──────────────────────────────
@router.message(UploadLesson.choosing_type)
async def choose_question_type(message: Message, state: FSMContext):
    data = await state.get_data()
    lesson_id = data.get("lesson_id")
    lesson_title = data.get("lesson_title")

    type_map = {
        "🖼 Картинка → слово": "image_word",
        "🇷🇺 Слово → перевод": "word_translate",
        "✏️ Фразы (ввод)": "phrase_translate",
    }
    q_type = type_map.get(message.text)
    if not q_type:
        await message.answer("Пожалуйста, выберите тип из кнопок ниже.")
        return

    await state.update_data(q_type=q_type)

    # Показываем информацию о загруженных вопросах
    counts = count_questions(lesson_id)
    lines = [f"📚 Урок: {lesson_title}"]
    lines.append(f"Загружено вопросов по типам:")
    total = 0
    for t, label in [("image_word", "🖼 Картинка → слово"),
                      ("word_translate", "🇷🇺 Слово → перевод"),
                      ("phrase_translate", "✏️ Фразы")]:
        c = counts.get(t, 0)
        total += c
        lines.append(f"  {label}: {c}")
    lines.append(f"  Всего: {total}")
    await message.answer("\n".join(lines))

    if q_type == "image_word":
        await message.answer(
            "Пришлите: КАРТИНКУ (фото) + подпись в формате:\n"
            "`немецкое_слово|русский_перевод|неправильный1|неправильный2|неправильный3`\n\n"
            "Пример: под фото написать:\n"
            "`der Vater|отец|die Mutter|der Bruder|das Kind`",
            reply_markup=kb.cancel_kb(),
        )
    elif q_type == "word_translate":
        await message.answer(
            "Пришлите в формате (одним сообщением):\n"
            "`немецкое_слово|русский_перевод|неправильный1|неправильный2|неправильный3`\n\n"
            "Пример:\n"
            "`der Tisch|стол|der Stuhl|das Bett|die Tür`",
            reply_markup=kb.cancel_kb(),
        )
    elif q_type == "phrase_translate":
        await message.answer(
            "Пришлите в формате (одним сообщением):\n"
            "`немецкая_фраза|русский_перевод`\n\n"
            "Пример:\n"
            "`Ich heiße Anna.|Меня зовут Анна.`",
            reply_markup=kb.cancel_kb(),
        )

    await state.set_state(UploadLesson.waiting_for_question)


# ─── Обработка вопроса ──────────────────────────────────────────────
@router.message(UploadLesson.waiting_for_question)
async def process_question(message: Message, state: FSMContext):
    data = await state.get_data()
    lesson_id = data["lesson_id"]
    q_type = data["q_type"]
    lesson_title = data["lesson_title"]

    if q_type == "image_word":
        # Должна быть фотография с подписью
        if not message.photo:
            await message.answer(
                "Для этого типа нужна фотография с подписью. Пришлите фото с описанием.",
                reply_markup=kb.cancel_kb(),
            )
            return

        caption = message.caption
        if not caption:
            await message.answer(
                "Добавьте подпись к фото в формате:\n"
                "`немецкое_слово|русский_перевод|неправильный1|неправильный2|неправильный3`",
                reply_markup=kb.cancel_kb(),
            )
            return

        file_id = message.photo[-1].file_id
        parts = parse_question_line(caption)
        if not parts:
            await message.answer(
                "❌ Неверный формат. Нужно: `слово|перевод|неправ1|неправ2|неправ3`\n"
                "Попробуйте ещё раз.",
                reply_markup=kb.cancel_kb(),
            )
            return

        word_de, word_ru, wrongs = parts
        add_question(
            lesson_id, q_type,
            word_de=word_de, word_ru=word_ru,
            wrong1_de=wrongs[0], wrong2_de=wrongs[1], wrong3_de=wrongs[2],
            image_id=file_id,
        )

        await message.answer(
            f"✅ Добавлен вопрос: «{word_de} — {word_ru}» (с картинкой)\n"
            "Можете добавить ещё один или нажмите /done чтобы закончить.",
            reply_markup=kb.cancel_kb(),
        )

    elif q_type == "word_translate":
        # Просто текст
        text = message.text
        if not text:
            await message.answer("Пришлите текстовое сообщение.", reply_markup=kb.cancel_kb())
            return

        parts = parse_question_line(text)
        if not parts:
            await message.answer(
                "❌ Неверный формат. Нужно: `слово|перевод|неправ1|неправ2|неправ3`\n"
                "Попробуйте ещё раз.",
                reply_markup=kb.cancel_kb(),
            )
            return

        word_de, word_ru, wrongs = parts
        add_question(
            lesson_id, q_type,
            word_de=word_de, word_ru=word_ru,
            wrong1_de=wrongs[0], wrong2_de=wrongs[1], wrong3_de=wrongs[2],
        )

        await message.answer(
            f"✅ Добавлен вопрос: «{word_de} — {word_ru}»\n"
            "Можете добавить ещё один или нажмите /done чтобы закончить.",
            reply_markup=kb.cancel_kb(),
        )

    elif q_type == "phrase_translate":
        text = message.text
        if not text:
            await message.answer("Пришлите текстовое сообщение.", reply_markup=kb.cancel_kb())
            return

        # Формат: фраза_нем|фраза_рус
        if "|" not in text:
            await message.answer(
                "❌ Формат: `немецкая_фраза|русский_перевод`\n"
                "Пример: `Ich heiße Anna.|Меня зовут Анна.`",
                reply_markup=kb.cancel_kb(),
            )
            return

        phrase_de, phrase_ru = text.split("|", 1)
        phrase_de = phrase_de.strip()
        phrase_ru = phrase_ru.strip()

        # Для фраз не нужно неправильных вариантов, но для единообразия сохраняем
        add_question(
            lesson_id, q_type,
            word_de=phrase_de, word_ru=phrase_ru,
            phrase_de=phrase_de, phrase_ru=phrase_ru,
        )

        await message.answer(
            f"✅ Добавлена фраза: «{phrase_de} — {phrase_ru}»\n"
            "Можете добавить ещё одну или нажмите /done чтобы закончить.",
            reply_markup=kb.cancel_kb(),
        )


# ─── /done — закончить загрузку ─────────────────────────────────────
@router.message(Command("done"))
async def done_upload(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data or "lesson_id" not in data:
        await message.answer("Нет активной загрузки.", reply_markup=kb.main_menu())
        return

    lesson_title = data.get("lesson_title", "")
    lesson_id = data["lesson_id"]
    counts = count_questions(lesson_id)
    total = sum(counts.values())

    await state.clear()
    await message.answer(
        f"🎉 Загрузка завершена!\n\n"
        f"📚 Урок: {lesson_title}\n"
        f"Всего вопросов: {total}\n\n"
        "Теперь можно играть! 🎮",
        reply_markup=kb.main_menu(),
    )


# ─── Вспомогательная функция ────────────────────────────────────────
def parse_question_line(text: str):
    """Парсит строку 'слово|перевод|непр1|непр2|непр3'."""
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 2:
        return None
    word_de = parts[0]
    word_ru = parts[1]
    wrongs = parts[2:5] if len(parts) >= 5 else ["", "", ""]
    # Дополняем до 3 неправильных, если меньше
    while len(wrongs) < 3:
        wrongs.append("")
    return word_de, word_ru, wrongs