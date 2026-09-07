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

# --- НАСТРОЙКА: ВСТАВЬТЕ СВОЙ ТОКЕН ---
BOT_TOKEN = "8821624488:AAGEWgFk1PJro7Va1Ipz1LS1Pt08eQAhjaM"  # ← ЗАМЕНИТЕ НА СВОЙ ТОКЕН
# --- НАСТРОЙКА ЗАВЕРШЕНА ---

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Инициализируем бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# --- РАСПИСАНИЕ ТУРНИРА ---
# Все команды
TEAMS = ["Белые", "Красные", "Фиолетовые", "Зелёные", "Черные"]

# Расписание по турам
# Формат: (Тур, Команда1, Команда2)
SCHEDULE = [
    # ТУР 1
    (1, "Белые", "Красные"),
    (1, "Фиолетовые", "Зелёные"),
    
    # ТУР 2
    (2, "Белые", "Черные"),
    (2, "Зелёные", "Красные"),
    
    # ТУР 3
    (3, "Белые", "Фиолетовые"),
    (3, "Черные", "Красные"),
    
    # ТУР 4
    (4, "Зелёные", "Черные"),
    (4, "Красные", "Фиолетовые"),
    
    # ТУР 5
    (5, "Белые", "Зелёные"),
    (5, "Фиолетовые", "Черные"),
    
    # ТУР 6
    (6, "Зелёные", "Фиолетовые"),
    (6, "Красные", "Белые"),
    
    # ТУР 7
    (7, "Красные", "Зелёные"),
    (7, "Черные", "Белые"),
    
    # ТУР 8
    (8, "Красные", "Черные"),
    (8, "Фиолетовые", "Белые"),
    
    # ТУР 9
    (9, "Фиолетовые", "Красные"),
    (9, "Черные", "Зелёные"),
    
    # ТУР 10
    (10, "Черные", "Фиолетовые"),
    (10, "Зелёные", "Белые"),
]

# Хранилище результатов матчей
# Ключ: (тур, команда1, команда2) -> (голы1, голы2)
match_results = {}

# --- КОНЕЦ РАСПИСАНИЯ ---

# Состояния для записи результата
class ResultStates(StatesGroup):
    waiting_for_match = State()
    waiting_for_goals = State()

# Глобальная переменная для хранения данных турнира
tournament_data = {}

def init_teams():
    """Инициализация данных всех команд"""
    for team in TEAMS:
        if team not in tournament_data:
            tournament_data[team] = {
                "goals_for": 0,
                "goals_against": 0,
                "points": 0,
                "matches": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0
            }

init_teams()

def get_resting_team(tour):
    """Определяет команду, которая отдыхает в туре (из 5 команд одна отдыхает)"""
    teams_in_tour = set()
    for t, team1, team2 in SCHEDULE:
        if t == tour:
            teams_in_tour.add(team1)
            teams_in_tour.add(team2)
    
    for team in TEAMS:
        if team not in teams_in_tour:
            return team
    return None

def get_played_matches():
    """Возвращает список сыгранных матчей"""
    played = []
    for tour, team1, team2 in SCHEDULE:
        if (tour, team1, team2) in match_results:
            played.append((tour, team1, team2))
    return played

def get_unplayed_matches():
    """Возвращает список несыгранных матчей"""
    unplayed = []
    for tour, team1, team2 in SCHEDULE:
        if (tour, team1, team2) not in match_results:
            unplayed.append((tour, team1, team2))
    return unplayed

def get_match_list_for_buttons():
    """Формирует список матчей для кнопок (только несыгранные)"""
    matches = []
    for tour, team1, team2 in SCHEDULE:
        if (tour, team1, team2) not in match_results:
            matches.append((team1, team2))
    return matches

# Команда /start - показать турнирную таблицу
@dp.message_handler(Command("start"))
async def show_table(message: Message):
    if not tournament_data:
        await message.answer("Турнирные данные еще не инициализированы.")
        return
    
    # Пересчитываем статистику из результатов
    recalculate_stats()
    
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["Команда", "Игры", "Очки", "Забито", "Пропущено", "Разница", "В", "Н", "П"])
    
    sorted_teams = sorted(tournament_data.items(), 
                         key=lambda x: (-x[1]['points'], -(x[1]['goals_for'] - x[1]['goals_against'])))
    
    for team, stats in sorted_teams:
        diff = stats['goals_for'] - stats['goals_against']
        writer.writerow([
            team, 
            stats['matches'], 
            stats['points'], 
            stats['goals_for'], 
            stats['goals_against'],
            diff,
            stats['wins'],
            stats['draws'],
            stats['losses']
        ])
    
    csv_content = output.getvalue()
    output.close()
    
    with open('table.csv', 'w', encoding='utf-8-sig') as f:
        f.write(csv_content)
    
    # Информация о сыгранных матчах
    played = len(get_played_matches())
    total = len(SCHEDULE)
    
    caption = f"📊 ТУРНИРНАЯ ТАБЛИЦА\nСыграно матчей: {played}/{total}"
    
    await message.answer_document(FSInputFile('table.csv'), caption=caption)
    os.remove('table.csv')

# Команда /add_result - начать процесс записи результата
@dp.message_handler(Command("add_result"))
async def ask_match(message: Message, state: FSMContext):
    unplayed = get_unplayed_matches()
    if not unplayed:
        await message.answer("🎉 ПОЗДРАВЛЯЮ! Все матчи уже сыграны! Турнир завершён!")
        return
    
    # Создаём кнопки для выбора матча
    buttons = []
    for tour, team1, team2 in unplayed:
        buttons.append([KeyboardButton(text=f"ТУР {tour}: {team1} — {team2}")])
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer("📋 Выберите матч для записи результата:", reply_markup=keyboard)
    await state.set_state(ResultStates.waiting_for_match)

# Команда /schedule - показать расписание
@dp.message_handler(Command("schedule"))
async def show_schedule(message: Message):
    text = "📅 РАСПИСАНИЕ ТУРНИРА\n\n"
    current_tour = 0
    
    for tour, team1, team2 in SCHEDULE:
        if tour != current_tour:
            current_tour = tour
            resting = get_resting_team(tour)
            text += f"\n🏆 ТУР {tour} —\n"
            if resting:
                text += f"🚬 {resting} (отдыхает)\n"
        
        # Проверяем, сыгран ли матч
        if (tour, team1, team2) in match_results:
            g1, g2 = match_results[(tour, team1, team2)]
            text += f"   • {team1} — {team2} {g1}-{g2} ✅\n"
        else:
            text += f"   • {team1} — {team2} ⏳\n"
    
    await message.answer(text)

# Команда /reset - сбросить все данные
@dp.message_handler(Command("reset"))
async def reset_data(message: Message):
    admin_id = 7911  # ← ВСТАВЬТЕ СВОЙ TELEGRAM ID
    if message.from_user.id != admin_id:
        await message.answer("⛔ У вас нет прав для этой команды.")
        return
    
    global tournament_data, match_results
    match_results = {}
    for team in TEAMS:
        tournament_data[team] = {
            "goals_for": 0,
            "goals_against": 0,
            "points": 0,
            "matches": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0
        }
    await message.answer("🔄 Все данные сброшены!")

def recalculate_stats():
    """Пересчитывает статистику на основе сохранённых результатов"""
    # Сбрасываем статистику
    for team in TEAMS:
        tournament_data[team] = {
            "goals_for": 0,
            "goals_against": 0,
            "points": 0,
            "matches": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0
        }
    
    # Пересчитываем по всем сыгранным матчам
    for (tour, team1, team2), (g1, g2) in match_results.items():
        # Команда 1
        tournament_data[team1]['goals_for'] += g1
        tournament_data[team1]['goals_against'] += g2
        tournament_data[team1]['matches'] += 1
        
        # Команда 2
        tournament_data[team2]['goals_for'] += g2
        tournament_data[team2]['goals_against'] += g1
        tournament_data[team2]['matches'] += 1
        
        if g1 > g2:
            tournament_data[team1]['points'] += 3
            tournament_data[team1]['wins'] += 1
            tournament_data[team2]['losses'] += 1
        elif g1 < g2:
            tournament_data[team2]['points'] += 3
            tournament_data[team2]['wins'] += 1
            tournament_data[team1]['losses'] += 1
        else:
            tournament_data[team1]['points'] += 1
            tournament_data[team2]['points'] += 1
            tournament_data[team1]['draws'] += 1
            tournament_data[team2]['draws'] += 1

# Обработчик выбора матча
@dp.message_handler(state=ResultStates.waiting_for_match)
async def process_match_selection(message: Message, state: FSMContext):
    selected_text = message.text
    match_found = False
    
    # Парсим текст: "ТУР 1: Белые — Красные"
    try:
        parts = selected_text.split(": ")
        tour_part = parts[0].replace("ТУР ", "")
        tour = int(tour_part)
        teams_part = parts[1].split(" — ")
        team1 = teams_part[0].strip()
        team2 = teams_part[1].strip()
        
        # Проверяем, что такой матч существует и не сыгран
        for t, t1, t2 in SCHEDULE:
            if t == tour and t1 == team1 and t2 == team2:
                if (tour, team1, team2) not in match_results:
                    await state.update_data(tour=tour, team1=team1, team2=team2)
                    await message.answer(
                        f"✅ Введите счёт для матча {team1} — {team2} в формате: X:Y (например, 2:1)",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    await state.set_state(ResultStates.waiting_for_goals)
                    match_found = True
                else:
                    await message.answer("❌ Этот матч уже сыгран!")
                    match_found = True
                break
    except:
        pass
    
    if not match_found:
        await message.answer("❌ Пожалуйста, выберите матч из списка, используя кнопки.")

# Обработчик счета
@dp.message_handler(state=ResultStates.waiting_for_goals)
async def process_goals(message: Message, state: FSMContext):
    try:
        goals = message.text.split(':')
        if len(goals) != 2:
            raise ValueError("Неверный формат. Используйте X:Y")
        
        g1 = int(goals[0])
        g2 = int(goals[1])
        
        data = await state.get_data()
        tour = data['tour']
        team1 = data['team1']
        team2 = data['team2']
        
        # Сохраняем результат
        match_results[(tour, team1, team2)] = (g1, g2)
        
        # Пересчитываем статистику
        recalculate_stats()
        
        await message.answer(f"✅ Результат матча {team1} {g1}:{g2} {team2} записан!")
        await state.finish()
        
        # Проверяем, остались ли матчи
        unplayed = get_unplayed_matches()
        if not unplayed:
            await message.answer("🎉 ПОЗДРАВЛЯЮ! Все матчи сыграны! Турнир завершён!")
        else:
            remaining = len(unplayed)
            await message.answer(f"📋 Осталось несыгранных матчей: {remaining}")
        
    except ValueError:
        await message.answer("❌ Неверный формат! Пожалуйста, введите счёт в формате X:Y, например, 2:1")

# Запуск бота
if __name__ == "__main__":
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
