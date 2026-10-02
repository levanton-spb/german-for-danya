from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


# ─── Reply-клавиатуры (текстовые кнопки снизу) ──────────────────────

def main_menu() -> ReplyKeyboardMarkup:
    """Главное меню."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🎮 Играть"),
        KeyboardButton(text="📚 Мои результаты"),
    )
    builder.row(
        KeyboardButton(text="🛠 Админ-панель"),
    )
    return builder.as_markup(resize_keyboard=True)


def game_type_choice() -> ReplyKeyboardMarkup:
    """Выбор типа игры."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🖼 Картинка → слово"),
    )
    builder.row(
        KeyboardButton(text="🇷🇺 Слово → перевод"),
    )
    builder.row(
        KeyboardButton(text="✏️ Фразы (ввод)"),
    )
    builder.row(
        KeyboardButton(text="◀️ Назад в меню"),
    )
    return builder.as_markup(resize_keyboard=True)


def cancel_kb() -> ReplyKeyboardMarkup:
    """Кнопка отмены."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Отмена")
    return builder.as_markup(resize_keyboard=True)


# ─── Inline-клавиатуры (кнопки под сообщением) ──────────────────────

def lessons_list(lessons, prefix: str = "choose_lesson") -> InlineKeyboardMarkup:
    """Список уроков в виде inline-кнопок."""
    builder = InlineKeyboardBuilder()
    for lesson in lessons:
        builder.row(
            InlineKeyboardButton(
                text=lesson["title"],
                callback_data=f"{prefix}:{lesson['id']}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"),
    )
    return builder.as_markup()


def answer_options(options: list[str], correct: str, prefix: str = "answer") -> InlineKeyboardMarkup:
    """Кнопки с вариантами ответа (1 из 4). На каждую вешаем callback."""
    # Перемешиваем, чтобы правильный не всегда был первым
    import random
    random.shuffle(options)

    builder = InlineKeyboardBuilder()
    for opt in options:
        builder.button(text=opt, callback_data=f"{prefix}:{opt}")
    builder.adjust(2)  # по 2 кнопки в ряд
    return builder.as_markup()


def result_action(lesson_id: int) -> InlineKeyboardMarkup:
    """Действия после окончания игры."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Повторить", callback_data=f"repeat:{lesson_id}"),
        InlineKeyboardButton(text="📊 В меню", callback_data="back_to_menu"),
    )
    return builder.as_markup()


def admin_menu() -> InlineKeyboardMarkup:
    """Меню администратора."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Загрузить урок", callback_data="admin_upload"),
    )
    builder.row(
        InlineKeyboardButton(text="📋 Список уроков", callback_data="admin_list"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu"),
    )
    return builder.as_markup()


def admin_lesson_actions(lesson_id: int) -> InlineKeyboardMarkup:
    """Действия над конкретным уроком (админ)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin_del:{lesson_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin_list"),
    )
    return builder.as_markup()


def confirm_delete(lesson_id: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления урока."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"admin_del_confirm:{lesson_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_list"),
    )
    return builder.as_markup()