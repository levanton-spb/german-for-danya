import sqlite3
import os
import random
from typing import Optional

DB_DIR = os.path.join(os.path.dirname(__file__), "data")


def get_connection() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    db_path = os.path.join(DB_DIR, "database.sqlite")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS lessons (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS questions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id   INTEGER NOT NULL,
            q_type      TEXT    NOT NULL CHECK(q_type IN ('image_word','word_translate','phrase_translate')),
            image_id    TEXT,            -- file_id из Telegram (для image_word)
            word_de     TEXT    NOT NULL,
            word_ru     TEXT    NOT NULL,
            wrong1_de   TEXT,
            wrong2_de   TEXT,
            wrong3_de   TEXT,
            phrase_de   TEXT,            -- для phrase_translate
            phrase_ru   TEXT,            -- для phrase_translate
            FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS results (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            lesson_id   INTEGER NOT NULL,
            q_type      TEXT    NOT NULL,
            total       INTEGER NOT NULL DEFAULT 0,
            correct     INTEGER NOT NULL DEFAULT 0,
            finished_at TEXT    NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()


# ─── CRUD для уроков ────────────────────────────────────────────────

def create_lesson(title: str) -> int:
    conn = get_connection()
    cursor = conn.execute("INSERT INTO lessons (title) VALUES (?)", (title,))
    lesson_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return lesson_id


def get_lessons() -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute("SELECT id, title, created_at FROM lessons ORDER BY created_at DESC").fetchall()
    conn.close()
    return rows


def get_lesson(lesson_id: int) -> Optional[sqlite3.Row]:
    conn = get_connection()
    row = conn.execute("SELECT id, title FROM lessons WHERE id=?", (lesson_id,)).fetchone()
    conn.close()
    return row


def delete_lesson(lesson_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM lessons WHERE id=?", (lesson_id,))
    conn.commit()
    conn.close()


# ─── CRUD для вопросов ──────────────────────────────────────────────

def add_question(
    lesson_id: int,
    q_type: str,
    word_de: str,
    word_ru: str,
    wrong1_de: str = "",
    wrong2_de: str = "",
    wrong3_de: str = "",
    image_id: str = "",
    phrase_de: str = "",
    phrase_ru: str = "",
) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO questions
           (lesson_id, q_type, image_id, word_de, word_ru, wrong1_de, wrong2_de, wrong3_de, phrase_de, phrase_ru)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (lesson_id, q_type, image_id, word_de, word_ru, wrong1_de, wrong2_de, wrong3_de, phrase_de, phrase_ru),
    )
    conn.commit()
    conn.close()


def get_questions(lesson_id: int, q_type: str, limit: int = 20) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM questions WHERE lesson_id=? AND q_type=? ORDER BY RANDOM() LIMIT ?",
        (lesson_id, q_type, limit),
    ).fetchall()
    conn.close()
    return rows


def count_questions(lesson_id: int) -> dict:
    conn = get_connection()
    rows = conn.execute(
        "SELECT q_type, COUNT(*) as cnt FROM questions WHERE lesson_id=? GROUP BY q_type",
        (lesson_id,),
    ).fetchall()
    conn.close()
    return {r["q_type"]: r["cnt"] for r in rows}


# ─── CRUD для результатов ───────────────────────────────────────────

def save_result(user_id: int, lesson_id: int, q_type: str, total: int, correct: int) -> int:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO results (user_id, lesson_id, q_type, total, correct) VALUES (?,?,?,?,?)",
        (user_id, lesson_id, q_type, total, correct),
    )
    result_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return result_id


def get_user_results(user_id: int, limit: int = 20) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT r.*, l.title as lesson_title
           FROM results r
           JOIN lessons l ON l.id = r.lesson_id
           WHERE r.user_id=?
           ORDER BY r.finished_at DESC
           LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return rows