import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import Message, FSInputFile
from aiogram.dispatcher import Dispatcher
from aiogram.dispatcher.filters import Command
from aiogram.dispatcher.fsm.context import FSMContext
from aiogram.dispatcher.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import csv
import io

# --- НАСТРОЙКА: ВСТАВЬТЕ СВОЙ ТОКЕН И РАСПИСАНИЕ ---
# 1. Вставьте сюда токен, который вы получили от @BotFather
BOT_TOKEN = "8821624488:AAGEWgFk1PJro7Va1Ipz1LS1Pt08eQAhjaM"  # ← ВСТАВЬТЕ СВОЙ ТОКЕН

# 2. Задайте расписание игр и команды.
SCHEDULE = [
    ("Зенит", "Спартак"),
    ("ЦСКА", "Динамо"),
    # Добавьте сюда все свои пары команд
]
# --- НАСТРОЙКА ЗАВЕРШЕНА ---

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Инициализируем бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Состояния для записи результата
class ResultStates(StatesGroup):
    waiting_for_match = State()
    waiting_for_goals = State()

# Глобальная переменная для хранения данных
tournament_data = {}

def init_teams():
    for team1, team2 in SCHEDULE:
        if team1 not in tournament_data:
            tournament_data[team1] = {"goals_for": 0, "goals_against": 0, "points": 0, "matches": 0}
        if team2 not in tournament_data:
            tournament_data[team2] = {"goals_for": 0, "goals_against": 0, "points": 0, "matches": 0}

init_teams()

# Команда /start - показать турнирную таблицу
@dp.message_handler(Command("start"))
async def show_table(message: Message):
    if not tournament_data:
        await message.answer("Турнирные данные еще не инициализированы. Проверьте код и токен.")
        return
    
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["Команда", "Игры", "Очки", "Забито", "Пропущено"])
    
    sorted_teams = sorted(tournament_data.items(), key=lambda x: (-x[1]['points'], -(x[1]['goals_for'] - x[1]['goals_against'])))
    for team, stats in sorted_teams:
        writer.writerow([team, stats['matches'], stats['points'], stats['goals_for'], stats['goals_against']])
    
    csv_content = output.getvalue()
    output.close()
    
    with open('table.csv', 'w', encoding='utf-8-sig') as f:
        f.write(csv_content)
    
    await message.answer_document(FSInputFile('table.csv'), caption="📊 Текущая турнирная таблица")
    os.remove('table.csv')

# Команда /add_result - начать процесс записи результата
@dp.message_handler(Command("add_result"))
async def ask_match(message: Message, state: FSMContext):
    if not SCHEDULE:
        await message.answer("Расписание матчей не задано в коде.")
        return
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=f"{team1} - {team2}")] for team1, team2 in SCHEDULE],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer("Выберите матч из списка ниже:", reply_markup=keyboard)
    await state.set_state(ResultStates.waiting_for_match)

# Обработчик выбора матча
@dp.message_handler(state=ResultStates.waiting_for_match)
async def process_match_selection(message: Message, state: FSMContext):
    selected_text = message.text
    match_found = False
    for team1, team2 in SCHEDULE:
        if selected_text == f"{team1} - {team2}":
            await state.update_data(team1=team1, team2=team2)
            await message.answer(f"✅ Отлично! Введите счет для матча {team1} - {team2} в формате: X:Y (например, 2:1)", reply_markup=ReplyKeyboardRemove())
            await state.set_state(ResultStates.waiting_for_goals)
            match_found = True
            break
    if not match_found:
        await message.answer("❌ Пожалуйста, выберите матч из списка, используя кнопки.")

# Обработчик счета
@dp.message_handler(state=ResultStates.waiting_for_goals)
async def process_goals(message: Message, state: FSMContext):
    try:
        goals = message.text.split(':')
        if len(goals) != 2:
            raise ValueError("Неверный формат. Используйте X:Y")
        
        team1_goals = int(goals[0])
        team2_goals = int(goals[1])
        
        data = await state.get_data()
        team1 = data['team1']
        team2 = data['team2']
        
        tournament_data[team1]['goals_for'] += team1_goals
        tournament_data[team1]['goals_against'] += team2_goals
        tournament_data[team1]['matches'] += 1
        if team1_goals > team2_goals:
            tournament_data[team1]['points'] += 3
        elif team1_goals == team2_goals:
            tournament_data[team1]['points'] += 1
        
        tournament_data[team2]['goals_for'] += team2_goals
        tournament_data[team2]['goals_against'] += team1_goals
        tournament_data[team2]['matches'] += 1
        if team2_goals > team1_goals:
            tournament_data[team2]['points'] += 3
        elif team1_goals == team2_goals:
            tournament_data[team2]['points'] += 1
        
        await message.answer(f"✅ Результат матча {team1} {team1_goals}:{team2_goals} {team2} записан!")
        await state.finish()
    except ValueError:
        await message.answer("❌ Неверный формат! Пожалуйста, введите счет в формате X:Y, например, 2:1")

# Запуск бота
if __name__ == "__main__":
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
