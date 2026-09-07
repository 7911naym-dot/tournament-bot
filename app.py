import logging
import csv
import io
import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes

# --- НАСТРОЙКА ---
BOT_TOKEN = "8821624488:AAGEwGfk1PJrO7Va1Ipz1LSlPt08eQAhjaM"  # ВАШ ТОКЕН
ADMIN_ID = 159790549  # ВАШ TELEGRAM ID
# --- КОНЕЦ НАСТРОЙКИ ---

logging.basicConfig(level=logging.INFO)

# Состояния разговора
WAITING_FOR_MATCH, WAITING_FOR_GOALS = range(2)

# Данные турнира
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

def get_unplayed_matches():
    return [(t, t1, t2) for t, t1, t2 in SCHEDULE if (t, t1, t2) not in match_results]

def get_played_matches():
    return [(t, t1, t2) for t, t1, t2 in SCHEDULE if (t, t1, t2) in match_results]

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    recalculate_stats()
    
    # Сортируем команды
    sorted_teams = sorted(tournament_data.items(), 
                         key=lambda x: (-x[1]['points'], -(x[1]['goals_for'] - x[1]['goals_against'])))
    
    # Создаём заголовок
    table = "🏆 <b>ТУРНИРНАЯ ТАБЛИЦА</b>\n"
    table += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Добавляем шапку таблицы (короткие названия колонок для телефона)
    table += "<code>"
    table += f"{'Команда':<10} {'И':<2} {'О':<2} {'З':<2} {'П':<2} {'±':<2} {'В':<1} {'Н':<1} {'П':<1}\n"
    table += "─────────────────────────────────\n"
    
    # Добавляем каждую команду
    for i, (team, stats) in enumerate(sorted_teams):
        diff = stats['goals_for'] - stats['goals_against']
        
        # Смайлы для мест
        if i == 0:
            medal = "🥇"
        elif i == 1:
            medal = "🥈"
        elif i == 2:
            medal = "🥉"
        elif i == 3:
            medal = "🍔"  # 4-е место — гамбургер
        else:
            medal = "🦴"  # 5-е место — кость
        
        # Обрезаем название до 8 символов, если длинное
        team_short = team[:8] if len(team) > 8 else team
        table += f"{medal} {team_short:<8} {stats['matches']:>2} {stats['points']:>2} {stats['goals_for']:>2} {stats['goals_against']:>2} {diff:>3} {stats['wins']:>1} {stats['draws']:>1} {stats['losses']:>1}\n"
    
    table += "</code>"
    
    # Информация о сыгранных матчах
    played = len(get_played_matches())
    total = len(SCHEDULE)
    table += f"\n📊 Сыграно: <b>{played}/{total}</b>"
    
    # Добавляем красивый футер
    table += "\n\n⚽ <i>Записать результат: /add_result</i>"
    
    await update.message.reply_text(table, parse_mode='HTML')

async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📅 <b>РАСПИСАНИЕ ТУРНИРА</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    current_tour = 0
    for tour, team1, team2 in SCHEDULE:
        if tour != current_tour:
            current_tour = tour
            resting = get_resting_team(tour)
            text += f"\n🏆 <b>ТУР {tour}</b>\n"
            if resting:
                text += f"🚬 {resting} <i>(отдыхает)</i>\n"
        
        if (tour, team1, team2) in match_results:
            g1, g2 = match_results[(tour, team1, team2)]
            if g1 > g2:
                result = f"✅ {team1} <b>{g1}</b> — {team2} <b>{g2}</b>"
            elif g1 < g2:
                result = f"✅ {team1} <b>{g1}</b> — {team2} <b>{g2}</b>"
            else:
                result = f"🤝 {team1} <b>{g1}</b> — {team2} <b>{g2}</b>"
            text += f"   • {result}\n"
        else:
            text += f"   • ⏳ {team1} — {team2}\n"
    
    await update.message.reply_text(text, parse_mode='HTML')

async def add_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    unplayed = get_unplayed_matches()
    if not unplayed:
        await update.message.reply_text("🎉 Все матчи сыграны! Турнир завершён!")
        return ConversationHandler.END
    buttons = [[KeyboardButton(text=f"ТУР {t}: {t1} — {t2}")] for t, t1, t2 in unplayed]
    keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("📋 Выберите матч:", reply_markup=keyboard)
    return WAITING_FOR_MATCH

async def handle_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    try:
        parts = text.split(": ")
        tour = int(parts[0].replace("ТУР ", ""))
        teams = parts[1].split(" — ")
        team1, team2 = teams[0].strip(), teams[1].strip()
        if (tour, team1, team2) in match_results:
            await update.message.reply_text("❌ Этот матч уже сыгран!")
            return WAITING_FOR_MATCH
        context.user_data['tour'] = tour
        context.user_data['team1'] = team1
        context.user_data['team2'] = team2
        await update.message.reply_text(f"✅ Введите счёт {team1} — {team2} (X:Y)", reply_markup=ReplyKeyboardRemove())
        return WAITING_FOR_GOALS
    except:
        await update.message.reply_text("❌ Выберите матч из списка!")
        return WAITING_FOR_MATCH

async def handle_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        g1, g2 = map(int, update.message.text.split(':'))
        tour = context.user_data['tour']
        team1 = context.user_data['team1']
        team2 = context.user_data['team2']
        match_results[(tour, team1, team2)] = (g1, g2)
        recalculate_stats()
        await update.message.reply_text(f"✅ {team1} {g1}:{g2} {team2} — записано!")
        remaining = len(get_unplayed_matches())
        if remaining == 0:
            await update.message.reply_text("🎉 ТУРНИР ЗАВЕРШЁН!")
        else:
            await update.message.reply_text(f"📋 Осталось матчей: {remaining}")
        return ConversationHandler.END
    except:
        await update.message.reply_text("❌ Неверный формат! Используйте X:Y (например, 2:1)")
        return WAITING_FOR_GOALS

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Нет прав!")
        return
    match_results.clear()
    init_teams()
    await update.message.reply_text("🔄 Все данные сброшены!")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
🤖 <b>Команды бота:</b>

/start - турнирная таблица
/schedule - расписание матчей
/add_result - записать результат
/reset - сброс данных (админ)
/help - помощь

📝 <b>Как записать результат:</b>
1. /add_result
2. Выбрать матч
3. Ввести X:Y (например, 2:1)
    """
    await update.message.reply_text(text, parse_mode='HTML')

# --- ЗАПУСК ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[CommandHandler("add_result", add_result)],
        states={
            WAITING_FOR_MATCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_match)],
            WAITING_FOR_GOALS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_goals)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("schedule", schedule))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(conv)
    
    app.run_polling()

if __name__ == "__main__":
    main()
