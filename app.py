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

BOT_TOKEN = "8821624488:AAGEWgFk1PJro7Va1Ipz1LS1Pt08eQAhjaM"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

TEAMS = ["Белые", "Красные", "Фиолетовые", "Зелёные", "Черные"]

SCHEDULE = [
    (1, "Белые", "Красные"),
    (1, "Фиолетовые", "Зелёные"),
    (2, "Белые", "Черные"),
    (2, "Зелёные", "Красные"),
    (3, "Белые", "Фиолетовые"),
    (3, "Черные", "Красные"),
    (4, "Зелёные", "Черные"),
    (4, "Красные", "Фиолетовые"),
    (5, "Белые", "Зелёные"),
    (5, "Фиолетовые", "Черные"),
    (6, "Зелёные", "Фиолетовые"),
    (6, "Красные", "Белые"),
    (7, "Красные", "Зелёные"),
    (7, "Черные", "Белые"),
    (8, "Красные", "Черные"),
    (8, "Фиолетовые", "Белые"),
    (9, "Фиолетовые", "Красные"),
    (9, "Черные", "Зелёные"),
    (10, "Черные", "Фиолетовые"),
    (10, "Зелёные", "Белые"),
]

match_results = {}

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
    played = []
    for tour, team1, team2 in SCHEDULE:
        if (tour, team1, team2) in match_results:
            played.append((tour, team1, team2))
    return played

def get_unplayed_matches():
    unplayed = []
    for tour, team1, team2 in SCHEDULE:
        if (tour, team1, team2) not in match_results:
            unplayed.append((tour, team1, team2))
    return unplayed

@dp.message_handler(Command("start"))
async def show_table(message: Message):
    recalculate_stats()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["Команда", "Игры", "Очки", "Забито", "Пропущено", "Разница", "В", "Н", "П"])
    sorted_teams = sorted(tournament_data.items(), 
                         key=lambda x: (-x[1]['points'], -(x[1]['goals_for'] - x[1]['goals_against'])))
    for team, stats in sorted_teams:
        diff = stats['goals_for'] - stats['goals_against']
        writer.writerow([team, stats['matches'], stats['points'], stats['goals_for'], stats['goals_against'], diff, stats['wins'], stats['draws'], stats['losses']])
    csv_content = output.getvalue()
    output.close()
    with open('table.csv', 'w', encoding='utf-8-sig') as f:
        f.write(csv_content)
    played = len(get_played_matches())
    total = len(SCHEDULE)
    caption = f"📊 ТУРНИРНАЯ ТАБЛИЦА\nСыграно матчей: {played}/{total}"
    await message.answer_document(FSInputFile('table.csv'), caption=caption)
    os.remove('table.csv')

@dp.message_handler(Command("add_result"))
async def ask_match(message: Message, state: FSMContext):
    unplayed = get_unplayed_matches()
    if not unplayed:
        await message.answer("🎉 ПОЗДРАВЛЯЮ! Все матчи уже сыграны! Турнир завершён!")
        return
    buttons = []
    for tour, team1, team2 in unplayed:
        buttons.append([KeyboardButton(text=f"ТУР {tour}: {team1} — {team2}")])
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)
    await message.answer("📋 Выберите матч для записи результата:", reply_markup=keyboard)
    await state.set_state(ResultStates.waiting_for_match)

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
        if (tour, team1, team2) in match_results:
            g1, g2 = match_results[(tour, team1, team2)]
            text += f"   • {team1} — {team2} {g1}-{g2} ✅\n"
        else:
            text += f"   • {team1} — {team2} ⏳\n"
    await message.answer(text)

@dp.message_handler(Command("reset"))
async def reset_data(message: Message):
    admin_id = 159790549
    if message.from_user.id != admin_id:
        await message.answer("⛔ У вас нет прав для этой команды.")
        return
    global tournament_data, match_results
    match_results = {}
    for team in TEAMS:
        tournament_data[team] = {"goals_for": 0, "goals_against": 0, "points": 0, "matches": 0, "wins": 0, "draws": 0, "losses": 0}
    await message.answer("🔄 Все данные сброшены!")

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

@dp.message_handler(state=ResultStates.waiting_for_match)
async def process_match_selection(message: Message, state: FSMContext):
    selected_text = message.text
    match_found = False
    try:
        parts = selected_text.split(": ")
        tour_part = parts[0].replace("ТУР ", "")
        tour = int(tour_part)
        teams_part = parts[1].split(" — ")
        team1 = teams_part[0].strip()
        team2 = teams_part[1].strip()
        for t, t1, t2 in SCHEDULE:
            if t == tour and t1 == team1 and t2 == team2:
                if (tour, team1, team2) not in match_results:
                    await state.update_data(tour=tour, team1=team1, team2=team2)
                    await message.answer(f"✅ Введите счёт для матча {team1} — {team2} в формате: X:Y (например, 2:1)", reply_markup=ReplyKeyboardRemove())
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
        match_results[(tour, team1, team2)] = (g1, g2)
        recalculate_stats()
        await message.answer(f"✅ Результат матча {team1} {g1}:{g2} {team2} записан!")
        await state.finish()
        unplayed = get_unplayed_matches()
        if not unplayed:
            await message.answer("🎉 ПОЗДРАВЛЯЮ! Все матчи сыграны! Турнир завершён!")
        else:
            remaining = len(unplayed)
            await message.answer(f"📋 Осталось несыгранных матчей: {remaining}")
    except ValueError:
        await message.answer("❌ Неверный формат! Пожалуйста, введите счёт в формате X:Y, например, 2:1")

if __name__ == "__main__":
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
