import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

# --- НАСТРОЙКА ---
BOT_TOKEN = "8821624488:AAGEwGfk1PJrO7Va1Ipz1LSlPt08eQAhjaM"
ADMIN_ID = 159790549
# --- КОНЕЦ НАСТРОЙКИ ---

logging.basicConfig(level=logging.INFO)

storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=storage)

# --- ТУРНИР: 3 КОМАНДЫ ---
TEAMS = ["Белые", "Синие", "Красные"]

# Возможные пары матчей (каждая команда играет с каждой)
MATCH_PAIRS = [
    ("Белые", "Синие"),
    ("Белые", "Красные"),
    ("Синие", "Красные"),
]

# match_results: список всех сыгранных матчей
# каждый элемент: {"team1": ..., "team2": ..., "g1": ..., "g2": ...}
match_results = []

class ResultStates(StatesGroup):
    waiting_for_match = State()
    waiting_for_goals = State()

tournament_data = {}

def init_teams():
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
init_teams()

def recalculate_stats():
    """Пересчитывает статистику на основе всех сыгранных матчей"""
    for team in TEAMS:
        tournament_data[team] = {"goals_for": 0, "goals_against": 0, "points": 0, "matches": 0, "wins": 0, "draws": 0, "losses": 0}
    
    for match in match_results:
        team1 = match["team1"]
        team2 = match["team2"]
        g1 = match["g1"]
        g2 = match["g2"]
        
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

def get_table_text():
    """Формирует текст турнирной таблицы"""
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
    table += f"\n📊 Всего сыграно матчей: <b>{len(match_results)}</b>"
    
    return table

def get_match_keyboard():
    """Создаёт клавиатуру со всеми возможными парами для выбора"""
    buttons = []
    for team1, team2 in MATCH_PAIRS:
        buttons.append([KeyboardButton(text=f"{team1} — {team2}")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)

# --- КОМАНДЫ БОТА ---

@dp.message(Command("start"))
async def start_command(message: Message, state: FSMContext):
    table = get_table_text()
    keyboard = get_match_keyboard()
    
    await message.answer(table, parse_mode='HTML')
    await message.answer("📋 Выберите матч для записи результата:", reply_markup=keyboard)
    await state.set_state(ResultStates.waiting_for_match)

@dp.message(Command("table"))
async def show_table(message: Message):
    table = get_table_text()
    await message.answer(table, parse_mode='HTML')

@dp.message(Command("schedule"))
async def show_schedule(message: Message):
    text = "📅 <b>СЫГРАННЫЕ МАТЧИ</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n"
    
    if not match_results:
        text += "\n⏳ Пока нет сыгранных матчей"
    else:
        for i, match in enumerate(match_results, 1):
            g1 = match["g1"]
            g2 = match["g2"]
            team1 = match["team1"]
            team2 = match["team2"]
            if g1 > g2:
                text += f"\n{i}. ✅ {team1} <b>{g1}</b> — {team2} <b>{g2}</b>"
            elif g1 < g2:
                text += f"\n{i}. ✅ {team1} <b>{g1}</b> — {team2} <b>{g2}</b>"
            else:
                text += f"\n{i}. 🤝 {team1} <b>{g1}</b> — {team2} <b>{g2}</b>"
    
    await message.answer(text, parse_mode='HTML')

@dp.message(Command("reset"))
async def reset_data(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав для этой команды.")
        return
    global match_results
    match_results = []
    init_teams()
    await state.clear()
    await message.answer("🔄 Все данные сброшены!")

@dp.message(Command("help"))
async def help_command(message: Message):
    text = """
🤖 <b>Команды бота:</b>

/start - начать запись матча (таблица + выбор)
/table - показать таблицу
/schedule - показать сыгранные матчи
/reset - сброс данных (админ)
/help - помощь

📝 <b>Как записать результат:</b>
1. Нажмите /start
2. Выберите пару команд из кнопок
3. Введите счёт в формате X:Y (например, 2:1)
4. Бот покажет таблицу и снова предложит выбрать матч

♻️ Количество игр не ограничено — можно играть сколько угодно!
    """
    await message.answer(text, parse_mode='HTML')

# --- ОБРАБОТЧИК ВЫБОРА МАТЧА ---

@dp.message(ResultStates.waiting_for_match)
async def process_match_selection(message: Message, state: FSMContext):
    text = message.text.strip()
    
    for team1, team2 in MATCH_PAIRS:
        if text == f"{team1} — {team2}":
            await state.update_data(team1=team1, team2=team2)
            await message.answer(
                f"✅ Введите счёт для матча <b>{team1} — {team2}</b> в формате X:Y (например, 2:1)",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode='HTML'
            )
            await state.set_state(ResultStates.waiting_for_goals)
            return
    
    await message.answer("❌ Пожалуйста, выберите матч из списка.")

# --- ОБРАБОТЧИК ВВОДА СЧЁТА ---

@dp.message(ResultStates.waiting_for_goals)
async def process_goals(message: Message, state: FSMContext):
    try:
        goals = message.text.split(':')
        if len(goals) != 2:
            raise ValueError("Неверный формат")
        g1 = int(goals[0])
        g2 = int(goals[1])
        data = await state.get_data()
        team1 = data['team1']
        team2 = data['team2']
        
        # Добавляем матч в список
        match_results.append({
            "team1": team1,
            "team2": team2,
            "g1": g1,
            "g2": g2
        })
        
        await message.answer(f"✅ Результат матча {team1} {g1}:{g2} {team2} записан!")
        
        # Показываем обновлённую таблицу
        table = get_table_text()
        await message.answer(table, parse_mode='HTML')
        
        # Снова предлагаем выбрать матч
        keyboard = get_match_keyboard()
        await message.answer("📋 Выберите следующий матч для записи результата:", reply_markup=keyboard)
        await state.set_state(ResultStates.waiting_for_match)
        
    except ValueError:
        await message.answer("❌ Неверный формат! Введите счёт в формате X:Y (например, 2:1)")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
