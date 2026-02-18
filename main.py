import os
from dotenv import load_dotenv
from gui import start_app

load_dotenv()  # подгружаем .env один раз для всего проекта

  # твоя основная функция запуска GUI

if __name__ == "__main__":
    start_app()