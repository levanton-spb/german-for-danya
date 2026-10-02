from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import keyboards as kb
import config
from database import get_lessons, get_user_results, get_lesson

router = Router()


# ─── FSM для выбора урока из списка (для игры) ──────────────────────
class LessonChoice(StatesGroup):
    choosing = State()


# ─── Команда /start ──────────────────────────────────────────────────
@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🇩🇪 Hallo! Добро пожаловать в Deutsch Lerner — игру для изучения немецкого языка!\n\n"
        "• Преподаватель загружает уроки с картинками, словами и фразами\n"
        "• Вы играете и отрабатываете пройденный материал\n"
        "• После 20 заданий — результат и оценка\n\n"
        "Выберите действие:",
        reply_markup=kb.main_menu(),
    )


# ─── Кнопка "Назад в меню" ──────────────────────────────────────────
@router.message(F.text == "◀️ Назад в меню")
async def back_to_menu_text(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню:", reply_markup=kb.main_menu())


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_cb(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("Главное меню:", reply_markup=kb.main_menu())
    await callback.answer()


# ─── Приветствие "вручную" ──────────────────────────────────────────
@router.message(F.text == "🎮 Играть")
async def play_button(message: Message):
    """Показываем выбор типа игры."""
    await message.answer(
        "Выберите тип заданий:",
        reply_markup=kb.game_type_choice(),
    )


# ─── Результаты ──────────────────────────────────────────────────────
@router.message(F.text == "📚 Мои результаты")
async def my_results(message: Message):
    results = get_user_results(message.from_user.id, limit=15)

    if not results:
        await message.answer(
            "У вас пока нет пройденных игр. Сыграйте и возвращайтесь! 🎮",
            reply_markup=kb.main_menu(),
        )
        return

    lines = ["📊 Ваши последние результаты:\n"]
    for r in results:
        grade = get_grade(r["correct"], r["total"])
        type_emoji = {
            "image_word": "🖼",
            "word_translate": "🇷🇺",
            "phrase_translate": "✏️",
        }.get(r["q_type"], "❓")
        lines.append(
            f"{type_emoji} «{r['lesson_title']}» — "
            f"{r['correct']}/{r['total']} {grade}"
        )

    await message.answer("\n".join(lines), reply_markup=kb.main_menu())


# ─── Админ-панель ───────────────────────────────────────────────────
@router.message(F.text == "🛠 Админ-панель")
async def admin_panel(message: Message):
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("⛔ У вас нет прав доступа к админ-панели.")
        return
    await message.answer(
        "🛠 Панель администратора:",
        reply_markup=kb.admin_menu(),
    )


# ─── Callback обработчики для админ-меню ────────────────────────────
@router.callback_query(F.data == "admin_upload")
async def admin_upload_start(callback: CallbackQuery):
    await callback.message.edit_text(
        "📤 Загрузите новый урок.\n\n"
        "Пришлите команду в формате:\n"
        "`/new_lesson Название урока`\n\n"
        "После этого бот проведёт вас по шагам загрузки.",
        reply_markup=kb.admin_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_list")
async def admin_list_lessons(callback: CallbackQuery):
    lessons = get_lessons()
    if not lessons:
        await callback.message.edit_text(
            "📋 Нет загруженных уроков.",
            reply_markup=kb.admin_menu(),
        )
        await callback.answer()
        return

    lines = ["📋 Список уроков:\n"]
    for lesson in lessons:
        lines.append(f"📚 {lesson['title']} (id: {lesson['id']})")

    # Показать список уроков inline кнопками для действий
    await callback.message.edit_text(
        "Выберите урок для управления:",
        reply_markup=kb.lessons_list(lessons, prefix="admin_manage"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_manage:"))
async def admin_manage_lesson(callback: CallbackQuery):
    lesson_id = int(callback.data.split(":")[1])
    lesson = get_lesson(lesson_id)
    if not lesson:
        await callback.answer("Урок не найден.")
        return

    await callback.message.edit_text(
        f"Управление уроком: «{lesson['title']}»",
        reply_markup=kb.admin_lesson_actions(lesson_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_del:"))
async def admin_del_lesson(callback: CallbackQuery):
    lesson_id = int(callback.data.split(":")[1])
    lesson = get_lesson(lesson_id)
    if not lesson:
        await callback.answer("Урок не найден.")
        return
    await callback.message.edit_text(
        f"⚠️ Вы уверены, что хотите удалить урок «{lesson['title']}»\n"
        "и все его вопросы? Это действие необратимо.",
        reply_markup=kb.confirm_delete(lesson_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_del_confirm:"))
async def admin_del_confirm(callback: CallbackQuery):
    from database import delete_lesson
    lesson_id = int(callback.data.split(":")[1])
    delete_lesson(lesson_id)
    await callback.message.edit_text(
        "✅ Урок удалён.",
        reply_markup=kb.admin_menu(),
    )
    await callback.answer()


# ─── Вспомогательная функция ────────────────────────────────────────
def get_grade(correct: int, total: int) -> str:
    if total == 0:
        return ""
    pct = correct / total
    if pct >= 0.95:
        return "🌟 Отлично!"
    elif pct >= 0.80:
        return "👍 Хорошо"
    elif pct >= 0.60:
        return "👌 Удовлетворительно"
    else:
        return "📚 Нужно повторить"