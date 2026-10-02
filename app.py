import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
import csv
import io

# --- НАСТРОЙКА: ВСТАВЬТЕ СВОЙ ТОКЕН ---
BOT_TOKEN = "8821624488:AAGEwGfk1PJrO7Va1Ipz1LSlPt08eQAhjaM"  # ← ЗАМЕНИТЕ НА СВОЙ ТОКЕН
ADMIN_ID = 159790549  # ← ВАШ TELEGRAM ID
# --- НАСТРОЙКА ЗАВЕРШЕНА ---

logging.basicConfig(level=logging.INFO)

storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=storage)

# --- ТУРНИР: 3 КОМАНДЫ ---
TEAMS = ["Красные", "Синие", "Белые"]

# match_results: ключ = (tour, team1, team2), значение = (g1, g2)
match_results = {}

# Счётчик туров (каждый тур — одна игра, третья команда отдыхает)
current_tour = 1

class ResultStates(StatesGroup):
    waiting_for_match = State()
    waiting_for_goals = State()

tournament_data = {}

def init_teams():
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
    """Определяет, какая команда отдыхает в туре (из 3 команд одна отдыхает)"""
    # Тур 1: играют 1-2, отдыхает 3
    # Тур 2: играют 1-3, отдыхает 2
    # Тур 3: играют 2-3, отдыхает 1
    # Далее цикл повторяется
    rest_index = (tour - 1) % 3
    return TEAMS[rest_index]

def get_match_for_tour(tour):
    """Возвращает пару команд для указанного тура"""
    rest_index = (tour - 1) % 3
    playing = [TEAMS[i] for i in range(3) if i != rest_index]
    return playing[0], playing[1]

def get_next_tour():
    """Возвращает номер следующего несыгранного тура"""
    tour = 1
    while (tour, get_match_for_tour(tour)[0], get_match_for_tour(tour)[1]) in match_results:
        tour += 1
    return tour

def get_played_matches():
    played = []
    for (tour, team1, team2) in match_results.keys():
        played.append((tour, team1, team2))
    return sorted(played, key=lambda x: x[0])

def recalculate_stats():
    for team in TEAMS:
        tournament_data[team] = {"goals_for": 0, "goals_against": 0, "points": 0, "matches": 0, "wins": 0, "draws": 0, "losses": 0}
    for (tour, team1, team2), (g1, g2) in match_results.items():
        tournament_data[team1]['goals_for'] += g1
        tournament_data[team1]['goals_against'] += g2
        tournament_data[team1]['matches'] += 1
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

# --- КОМАНДЫ БОТА ---

@dp.message(Command("start"))
async def show_table(message: Message):
    recalculate_stats()
    
    sorted_teams = sorted(tournament_data.items(), 
                         key=lambda x: (-x[1]['points'], -(x[1]['goals_for'] - x[1]['goals_against'])))
    
    table = "🏆 <b>ТУРНИРНАЯ ТАБЛИЦА</b> 🏆\n\n"
    table += "<code>"
    table += "Команда  И В Н П З П ± О\n"
    table += "─────────────────────────\n"
    
    for i, (team, stats) in enumerate(sorted_teams):
        diff = stats['goals_for'] - stats['goals_against']
        if diff > 0:
            diff_str = f"+{diff}"
        else:
            diff_str = str(diff)
        
        team_short = team[:7]
        table += f"{team_short:<8} {stats['matches']:>1} {stats['wins']:>1} {stats['draws']:>1} {stats['losses']:>1} {stats['goals_for']:>1} {stats['goals_against']:>1} {diff_str:>2} {stats['points']:>1}\n"
    
    table += "</code>"
    
    played = len(get_played_matches())
    next_tour = get_next_tour()
    table += f"\n📊 Сыграно матчей: <b>{played}</b>"
    table += f"\n📅 Следующий тур: <b>{next_tour}</b>"
    table += "\n\n⚽ <i>/add_result</i> | 📅 <i>/schedule</i>"
    
    await message.answer(table, parse_mode='HTML')

@dp.message(Command("schedule"))
async def show_schedule(message: Message):
    text = "📅 <b>РАСПИСАНИЕ ТУРНИРА</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n"
    
    # Показываем все сыгранные туры + следующие 5 туров
    played = get_played_matches()
    last_played_tour = max([t for t, _, _ in played], default=0)
    
    max_tour = max(last_played_tour + 5, 5)
    
    for tour in range(1, max_tour + 1):
        team1, team2 = get_match_for_tour(tour)
        resting = get_resting_team(tour)
        
        text += f"\n🏆 <b>ТУР {tour}</b>\n"
        text += f"🚬 {resting} (отдыхает)\n"
        
        if (tour, team1, team2) in match_results:
            g1, g2 = match_results[(tour, team1, team2)]
            if g1 > g2:
                text += f"   • ✅ {team1} <b>{g1}</b> — {team2} <b>{g2}</b>\n"
            elif g1 < g2:
                text += f"   • ✅ {team1} <b>{g1}</b> — {team2} <b>{g2}</b>\n"
            else:
                text += f"   • 🤝 {team1} <b>{g1}</b> — {team2} <b>{g2}</b>\n"
        else:
            text += f"   • ⏳ {team1} — {team2}\n"
    
    await message.answer(text, parse_mode='HTML')

@dp.message(Command("add_result"))
async def ask_match(message: Message, state: FSMContext):
    tour = get_next_tour()
    team1, team2 = get_match_for_tour(tour)
    resting = get_resting_team(tour)
    
    text = f"📋 <b>ТУР {tour}</b>\n"
    text += f"🚬 {resting} (отдыхает)\n"
    text += f"⚽ Играют: <b>{team1}</b> — <b>{team2}</b>\n\n"
    text += f"Введите счёт в формате X:Y (например, 2:1)"
    
    await message.answer(text, parse_mode='HTML')
    await state.update_data(tour=tour, team1=team1, team2=team2)
    await state.set_state(ResultStates.waiting_for_goals)

@dp.message(Command("reset"))
async def reset_data(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав для этой команды.")
        return
    global match_results
    match_results = {}
    init_teams()
    await message.answer("🔄 Все данные сброшены!")

@dp.message(Command("help"))
async def help_command(message: Message):
    text = """
🤖 <b>Команды бота:</b>

/start - турнирная таблица
/schedule - расписание туров
/add_result - записать результат
/reset - сброс данных (админ)
/help - помощь

📝 <b>Как записать результат:</b>
1. Нажмите /add_result
2. Бот покажет, кто играет в следующем туре
3. Введите счёт в формате X:Y (например, 2:1)

🚬 В каждом туре одна команда отдыхает.
    """
    await message.answer(text, parse_mode='HTML')

@dp.message(ResultStates.waiting_for_goals)
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
        match_results[(tour, team1, team2)] = (g1, g2)
        recalculate_stats()
        await message.answer(f"✅ Результат матча {team1} {g1}:{g2} {team2} записан!")
        await state.clear()
        
        next_tour = get_next_tour()
        next_team1, next_team2 = get_match_for_tour(next_tour)
        next_resting = get_resting_team(next_tour)
        await message.answer(
            f"📋 Следующий тур: <b>{next_tour}</b>\n"
            f"🚬 {next_resting} (отдыхает)\n"
            f"⚽ {next_team1} — {next_team2}\n\n"
            f"Чтобы записать результат, нажмите /add_result",
            parse_mode='HTML'
        )
    except ValueError:
        await message.answer("❌ Неверный формат! Пожалуйста, введите счёт в формате X:Y, например, 2:1")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
