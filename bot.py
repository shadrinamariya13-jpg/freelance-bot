"""
Freelance Monitor Bot v4 — GitHub Actions
Запускается по расписанию, делает одну проверку, шлёт дайджест, останавливается.
"""

import asyncio
import aiohttp
import json
import os
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()])
log = logging.getLogger(__name__)

BOT_TOKEN      = "6150748269:AAGBh9h-NRqJu6WrXyiTQifAE_6bSuS43vU"
OWNER_ID       = 1709442669
MIN_BUDGET     = 5000
URGENT_BUDGET  = 30000
MAX_RESPONSES  = 30
MIN_TEXT_LEN   = 80
MIN_SCORE      = 3
DIGEST_TOP     = 5
TZ_OFFSET      = 3
STATE_FILE     = "seen_posts.json"

CHANNELS = [
    "ipomogator", "Koteyka_Freelancer", "frilanser_vacansii",
    "distantsiya", "workzavr", "designer_ru", "designer_jobs",
    "frilanc", "THE_POMOGATOR",
]

NICHES = {
    "📝 Тексты": ["текст", "статья", "статью", "копирайт", "копирайтер",
        "написать", "написание", "рерайт", "обзор", "описание услуг",
        "медицинский текст", "косметолог", "строительный текст",
        "образовательный контент", "туристический", "психологическ", "инструкция"],
    "🌐 Переводы": ["перевод", "переводчик", "перевести", "translate",
        "с английского", "на английский", "технический перевод",
        "медицинский перевод", "юридический перевод"],
    "🎨 Дизайн": ["дизайн", "дизайнер", "баннер", "логотип", "макет", "figma",
        "иллюстрация", "инфографика", "брендинг", "визуал", "сторис", "оформление"],
    "💻 IT и код": ["бот", "telegram бот", "python", "скрипт", "парсер",
        "лендинг", "landing", "html", "верстка", "автоматизация",
        "чат-бот", "gpt бот", "api", "интеграция", "написать код"],
    "📊 Презентации": ["презентация", "powerpoint", "pitch deck", "слайды", "pptx"],
    "📐 Схемы": ["схема", "чертёж", "чертеж", "блок-схема", "flowchart"],
    "📅 Контент и SMM": ["контент-план", "контент план", "smm", "ведение соцсетей", "контент стратегия"],
    "⚖️ Юридика": ["договор", "юридический текст", "оферта", "политика конфиденциальности"],
    "🏖️ Туризм": ["туристическ", "отель описание", "маршрут", "экскурси", "путеводитель"],
    "📈 SEO": ["seo", "сео", "семантическое ядро", "ключевые слова", "метатеги", "seo аудит"],
    "🎯 Анализ": ["анализ конкурент", "анализ целевой", "анализ цА", "исследование рынка",
        "портрет клиента", "custdev", "swot"],
    "📊 Таблицы": ["excel", "гугл таблиц", "google sheets", "таблица", "формулы",
        "заполнить таблицу", "обработка данных", "чистка данных", "дашборд"],
}

LOW_COMPETITION = {"📐 Схемы", "💻 IT и код", "⚖️ Юридика", "🎯 Анализ", "📊 Таблицы", "🌐 Переводы"}

REPLIES = {
    "📝 Тексты": "Добрый день! Пишу тексты под вашу тему — медицина, косметология, стройка, образование. Есть примеры. Когда удобно обсудить?",
    "🌐 Переводы": "Здравствуйте! Делаю переводы RU↔EN: технические, медицинские, юридические. Точно в срок. Могу прислать тестовый фрагмент.",
    "🎨 Дизайн": "Добрый день! Создаю баннеры, макеты, иллюстрации под любой стиль. Вышлю портфолио. Готов приступить быстро.",
    "💻 IT и код": "Здравствуйте! Пишу скрипты, боты, парсеры, лендинги. Опишите задачу — дам точную оценку по времени и стоимости.",
    "📊 Презентации": "Добрый день! Делаю презентации с нуля: структура, текст, дизайн. Покажу примеры. Когда нужна готовая работа?",
    "📐 Схемы": "Здравствуйте! Оформляю схемы, чертежи, блок-схемы чётко и по ТЗ. Уточните формат и объём.",
    "📅 Контент и SMM": "Добрый день! Разрабатываю контент-планы и SMM-стратегии. Готов показать пример. Обсудим?",
    "⚖️ Юридика": "Здравствуйте! Составляю договоры, оферты, политики конфиденциальности. Уточните задачу?",
    "🏖️ Туризм": "Добрый день! Пишу описания отелей, маршруты, туристические тексты. Покажу примеры.",
    "📈 SEO": "Здравствуйте! Провожу SEO-аудит, собираю семантику, пишу метатеги. Покажу пример отчёта.",
    "🎯 Анализ": "Добрый день! Делаю анализ ЦА, конкурентов, исследования рынка с отчётом. Уточните что нужно?",
    "📊 Таблицы": "Здравствуйте! Работаю с Excel и Google Sheets: формулы, сводные, чистка данных. Опишите задачу.",
}

SPAM_WORDS = [
    "казино", "ставки", "крипт", "форекс", "заработай за 1 день",
    "схема заработка", "реферальн", "mlm", "сетевой маркетинг",
    "100% доход", "без вложений", "пассивный доход", "бинар",
    "карточки маркетплейс", "карточки озон", "карточки вайлдберриз",
    "карточки wildberries", "карточки ozon",
    # Вакансии и найм
    "вакансия", "#вакансия", "ищу сотрудника", "ищем сотрудника",
    "набор сотрудников", "трудоустройство", "официальное трудоустройство",
    "з/п", "зарплата", "оклад", "занятость", "полная занятость",
    "3-4 часа в день", "часов в день", "личный ассистент",
    "помощник руководителя", "удалённая работа", "удаленная работа",
    "работа на дому", "подработка на дому", "центр трудоустройства",
    "проходишь обучение", "набор людей", "контент-завод",
    "топ-менеджер", "#требуется", "#ищу", "smm специалист",
]

FRAUD_WORDS = [
    "после сдачи оплачу", "оплата по факту", "тестовое задание бесплатно",
    "доверяю на слово", "предоплата не нужна", "сначала работа потом деньги",
]

LONGTERM_WORDS = [
    "долгосрочн", "постоянн", "регулярн", "на постоянной основе",
    "тестовый заказ", "первый заказ из серии", "возможно продолжение",
    "дальнейшее сотрудничество",
]

BUDGET_RE = re.compile(r"(\d[\d\s]{1,6})\s*(руб|₽|rub|тыс\.?|к\b|k\b)", re.IGNORECASE)
RESPONSES_RE = re.compile(r"(\d+)\s*(отклик|ответ|предложени)", re.IGNORECASE)

def load_seen() -> set:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_seen(seen: set):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, ensure_ascii=False)

def detect_niche(text: str) -> Optional[str]:
    tl = text.lower()
    for niche, kws in NICHES.items():
        if any(kw in tl for kw in kws):
            return niche
    return None

def is_spam(text: str) -> bool:
    tl = text.lower()
    return any(w in tl for w in SPAM_WORDS)

def is_fraud(text: str) -> bool:
    tl = text.lower()
    return any(w in tl for w in FRAUD_WORDS)

def is_longterm(text: str) -> bool:
    tl = text.lower()
    return any(w in tl for w in LONGTERM_WORDS)

def extract_budget(text: str) -> tuple:
    m = BUDGET_RE.search(text)
    if not m:
        return "не указан", 0
    num = int(m.group(1).replace(" ", ""))
    unit = m.group(2).lower().rstrip(".")
    if unit in ("тыс", "к", "k"):
        num *= 1000
    return f"{num:,} ₽".replace(",", " "), num

def extract_responses(text: str) -> int:
    m = RESPONSES_RE.search(text)
    return int(m.group(1)) if m else 0

def score_order(order: dict) -> int:
    score = 0
    tl = order["text"].lower()
    b = order["budget_num"]
    if b >= 30000:   score += 4
    elif b >= 15000: score += 3
    elif b >= 10000: score += 2
    elif b >= 5000:  score += 1
    if any(w in tl for w in ["тз", "техническое задание", "требования", "срок", "дедлайн"]):
        score += 1
    if order["niche"] in LOW_COMPETITION:
        score += 2
    if order["longterm"]:
        score += 2
    r = order["responses"]
    if r == 0:    score += 1
    elif r <= 10: score += 1
    if len(order["text"]) > 300:
        score += 1
    return score

async def fetch_channel(session, channel: str) -> list:
    url = f"https://t.me/s/{channel}"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"}
    posts = []
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as r:
            if r.status != 200:
                return posts
            html = await r.text()
        blocks = re.findall(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
        ids = re.findall(r'data-post="[^/]+/(\d+)"', html)
        for i, block in enumerate(blocks):
            text = re.sub(r"<br\s*/?>", "\n", block)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"[ \t]+", " ", text).strip()
            text = text.replace("&amp;","&").replace("&lt;","<").replace("&gt;",">").replace("&#34;",'"').replace("&nbsp;"," ")
            pid = ids[i] if i < len(ids) else f"p{i}"
            posts.append({"id": f"{channel}_{pid}", "text": text, "channel": channel})
    except Exception as e:
        log.warning(f"{channel}: {e}")
    return posts

async def send_tg(session, text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    if len(text) > 4000:
        text = text[:3990] + "\n…"
    try:
        async with session.post(url, json={"chat_id": OWNER_ID, "text": text,
                "parse_mode": "HTML", "disable_web_page_preview": True},
                timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status != 200:
                log.warning(f"sendMessage {r.status}")
    except Exception as e:
        log.warning(f"sendMessage: {e}")

def moscow_hour() -> int:
    return datetime.now(timezone(timedelta(hours=TZ_OFFSET))).hour

def is_morning() -> bool:
    return moscow_hour() == 8

def format_order(o: dict, i: int) -> str:
    preview = o["text"][:220].replace("\n", " ")
    if len(o["text"]) > 220:
        preview += "…"
    reply = REPLIES.get(o["niche"], "Готов взяться за вашу задачу. Уточните детали?")
    flags = []
    if o["longterm"]: flags.append("🔁 долгосрок")
    if o["responses"] == 0: flags.append("👤 0 откликов")
    elif o["responses"] <= 10: flags.append(f"👤 {o['responses']} откл.")
    if o["niche"] in LOW_COMPETITION: flags.append("🎯 низкая конкуренция")
    flag_str = "  ".join(flags)
    return (
        f"<b>{i}. {o['niche']}</b>  •  @{o['channel']}\n"
        f"💰 {o['budget_str']}   ⭐ {o['score']}/10"
        + (f"\n{flag_str}" if flag_str else "") +
        f"\n\n{preview}\n\n"
        f"✍️ <i>{reply}</i>\n"
    )

async def main():
    seen = load_seen()
    log.info(f"Старт. Видено ранее: {len(seen)}")
    orders = []
    urgent = []

    async with aiohttp.ClientSession() as session:
        for channel in CHANNELS:
            posts = await fetch_channel(session, channel)
            for post in posts:
                if post["id"] in seen:
                    continue
                seen.add(post["id"])
                text = post["text"]
                if len(text) < MIN_TEXT_LEN or is_spam(text) or is_fraud(text):
                    continue
                niche = detect_niche(text)
                if not niche:
                    continue
                budget_str, budget_num = extract_budget(text)
                if budget_num == 0 or budget_num < MIN_BUDGET:
                    continue
                responses = extract_responses(text)
                if responses > MAX_RESPONSES:
                    continue
                longterm = is_longterm(text)
                order = {
                    "niche": niche, "channel": channel, "text": text,
                    "budget_str": budget_str, "budget_num": budget_num,
                    "responses": responses, "longterm": longterm,
                }
                order["score"] = score_order(order)
                if order["score"] < MIN_SCORE:
                    continue
                if budget_num >= URGENT_BUDGET or longterm:
                    urgent.append(order)
                else:
                    orders.append(order)
            await asyncio.sleep(2)

        save_seen(seen)
        log.info(f"Срочных: {len(urgent)}, обычных: {len(orders)}")

        # Срочные — шлём сразу по одному
        for o in urgent:
            tag = "🔥 СРОЧНО — высокий бюджет" if o["budget_num"] >= URGENT_BUDGET else "🔁 СРОЧНО — долгосрок"
            preview = o["text"][:300].replace("\n", " ")
            reply = REPLIES.get(o["niche"], "Готов взяться за вашу задачу.")
            msg = (f"{tag}\n\n<b>{o['niche']}</b>  •  @{o['channel']}\n"
                   f"💰 {o['budget_str']}   ⭐ {o['score']}/10\n\n"
                   f"{preview}\n\n━━━━━━━━━━━━━━━\n"
                   f"✍️ <b>Готовый отклик:</b>\n<i>{reply}</i>")
            await send_tg(session, msg)
            await asyncio.sleep(1)

        # Дайджест
        all_orders = sorted(orders, key=lambda x: x["score"], reverse=True)
        top_n = 40 if is_morning() else DIGEST_TOP
        top = all_orders[:top_n]

        if not top and not urgent:
            log.info("Новых подходящих заказов нет.")
            return

        if top:
            now_msk = datetime.now(timezone(timedelta(hours=TZ_OFFSET)))
            title = f"Доброе утро! Заказы за ночь 🌅" if is_morning() else f"Дайджест {now_msk.strftime('%H:%M')}"
            header = f"📋 <b>{title}</b>\nНайдено: <b>{len(orders)}</b>  •  Показываю топ <b>{len(top)}</b>\n\n"
            current = header
            sep = "─" * 28 + "\n"
            msgs = []
            for i, o in enumerate(top, 1):
                block = sep + format_order(o, i)
                if len(current) + len(block) > 3800:
                    msgs.append(current)
                    current = f"📋 <b>{title}</b> (продолжение)\n\n" + block
                else:
                    current += block
            msgs.append(current)
            for m in msgs:
                await send_tg(session, m)
                await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
