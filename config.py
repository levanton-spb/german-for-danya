import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DATABASE_PATH = "data/database.sqlite"

# Настройки игры
QUESTIONS_PER_ROUND = 20
CORRECT_ANSWERS_TO_PASS = 15  # для оценки "отлично"