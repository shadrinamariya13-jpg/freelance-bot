"""
Freelance Monitor Bot v3
— Дайджест раз в 2 часа (топ 5), утром в 8:00 (топ 20-50)
— Тихие часы 21:00–08:00
— Срочные уведомления: бюджет 30к+ или долгосрок
— Антифрод, скоринг, фильтры качества
"""

import asyncio
import aiohttp
import json
import os
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("bot.log", encoding="utf-8")]
)
log = logging.getLogger(__name__)

# ══════════════════════════════════════════════
#  НАСТРОЙКИ
# ══════════════════════════════════════════════
BOT_TOKEN         = "6150748269:AAGBh9h-NRqJu6WrXyiTQifAE_6bSuS43vU"
OWNER_ID          = 1709442669
DIGEST_INTERVAL   = 7200    # 2 часа между дневными дайджестами
MIN_BUDGET        = 5000    # ₽
URGENT_BUDGET     = 30000   # ₽ — слать сразу
MAX_RESPONSES     = 30      # если откликов больше — пропускаем
MIN_TEXT_LEN      = 80      # минимум символов в заказе
MIN_SCORE         = 3       # минимальный балл для попадания в дайджест
DIGEST_TOP_DAY    = 5       # заказов в дневном дайджесте
DIGEST_TOP_NIGHT  = 40      # заказов в утреннем дайджесте (за ночь)
MIN_ORDERS_TO_SEND = 3      # меньше — не слать, копить до следующего
QUIET_START       = 21      # час начала тихого времени
QUIET_END         = 8       # час конца тихого времени
TZ_OFFSET         = 3       # UTC+3 Москва
STATE_FILE        = "seen_posts.json"

CHANNELS = [
    "ipomogator",
    "Koteyka_Freelancer",
    "frilanser_vacansii",
    "distantsiya",
    "workzavr",
    "designer_ru",
    "designer_jobs",
    "frilanc",
    "THE_POMOGATOR",
]

# ══════════════════════════════════════════════
#  НИШИ
# ══════════════════════════════════════════════
NICHES = {
    "📝 Тексты": [
        "текст", "статья", "статью", "копирайт", "копирайтер",
        "написать", "написание", "рерайт", "обзор", "описание услуг",
        "медицинский текст", "косметолог текст", "строительный текст",
        "образовательный контент", "туристический текст",
        "психологическ", "инструкция", "документация",
    ],
    "🌐 Переводы": [
        "перевод", "переводчик", "перевести", "translate",
        "с английского", "на английский", "технический перевод",
        "медицинский перевод", "юридический перевод", "перевод документ",
    ],
    "🎨 Дизайн": [
        "дизайн", "дизайнер", "баннер", "логотип", "макет", "figma",
        "иллюстрация", "инфографика", "брендинг", "визуал",
        "сторис", "оформление", "соцсети дизайн", "фирменный стиль",
    ],
    "💻 IT и код": [
        "бот", "telegram бот", "python", "скрипт", "парсер", "парсинг",
        "лендинг", "landing", "html", "верстка", "автоматизация",
        "чат-бот", "gpt бот", "api", "интеграция", "crm",
        "написать код", "разработать", "программист",
    ],
    "📊 Презентации": [
        "презентация", "powerpoint", "pitch deck", "слайды", "pptx",
        "презентация для инвестор", "бизнес презентация",
    ],
    "📐 Схемы и чертежи": [
        "схема", "чертёж", "чертеж", "блок-схема", "flowchart",
        "техническое задание составить", "visio", "drawio",
    ],
    "📅 Контент и SMM": [
        "контент-план", "контент план", "smm", "ведение соцсетей",
        "контент стратегия", "контент менеджер", "посты для",
    ],
    "⚖️ Юридика": [
        "договор", "юридический текст", "оферта", "политика конфиденциальности",
        "пользовательское соглашение", "правовой", "юрист текст",
    ],
    "🏖️ Туризм": [
        "туристическ", "отель описание", "маршрут", "экскурси",
        "путеводитель", "тур описание",
    ],
    "📈 SEO": [
        "seo", "сео", "семантическое ядро", "ключевые слова", "метатеги",
        "seo аудит", "продвижение сайта", "позиции сайта", "robots.txt",
        "перелинковка", "техническое seo",
    ],
    "🎯 Анализ ЦА и конкурентов": [
        "анализ конкурент", "анализ целевой аудитории", "анализ цА",
        "исследование рынка", "портрет клиента", "custdev",
        "маркетинговый анализ", "swot", "бриф",
    ],
    "📊 Таблицы и данные": [
        "excel", "гугл таблиц", "google sheets", "таблица",
        "сводная таблица", "формулы", "заполнить таблицу",
        "обработка данных", "фильтрация данных", "чистка данных",
        "база данных", "парсинг данных", "дашборд",
    ],
}

# Ниши с низкой конкуренцией — приоритет в скоринге
LOW_COMPETITION_NICHES = {
    "📐 Схемы и чертежи",
    "💻 IT и код",
    "⚖️ Юридика",
    "🎯 Анализ ЦА и конкурентов",
    "📊 Таблицы и данные",
    "🌐 Переводы",
}

REPLIES = {
    "📝 Тексты": "Добрый день! Пишу тексты под вашу тему — медицина, косметология, стройка, образование. Есть примеры. Когда удобно обсудить?",
    "🌐 Переводы": "Здравствуйте! Делаю переводы RU↔EN: технические, медицинские, юридические. Точно в срок. Могу прислать тестовый фрагмент.",
    "🎨 Дизайн": "Добрый день! Создаю баннеры, макеты, иллюстрации под любой стиль. Вышлю портфолио по вашей теме. Готов приступить быстро.",
    "💻 IT и код": "Здравствуйте! Пишу скрипты, боты, парсеры, лендинги. Опишите задачу подробнее — дам точную оценку по времени и стоимости.",
    "📊 Презентации": "Добрый день! Делаю презентации с нуля: структура, текст, дизайн слайдов. Покажу примеры. Когда нужна готовая работа?",
    "📐 Схемы и чертежи": "Здравствуйте! Оформляю схемы, чертежи, блок-схемы чётко и по ТЗ. Уточните формат и объём — сделаем быстро.",
    "📅 Контент и SMM": "Добрый день! Разрабатываю контент-планы и SMM-стратегии под вашу аудиторию. Готов показать пример. Обсудим?",
    "⚖️ Юридика": "Здравствуйте! Составляю договоры, оферты, политики конфиденциальности. Грамотно и по существу. Уточните задачу?",
    "🏖️ Туризм": "Добрый день! Пишу описания отелей, маршруты, туристические тексты. Покажу примеры. Когда удобно обсудить?",
    "📈 SEO": "Здравствуйте! Провожу SEO-аудит, собираю семантику, пишу метатеги. Покажу пример отчёта. Обсудим задачу?",
    "🎯 Анализ ЦА и конкурентов": "Добрый день! Делаю анализ ЦА, конкурентов, исследования рынка с отчётом. Уточните что именно нужно?",
    "📊 Таблицы и данные": "Здравствуйте! Работаю с Excel и Google Sheets: формулы, сводные, чистка и обработка данных. Опишите задачу подробнее.",
}

# ══════════════════════════════════════════════
#  СТОП-СЛОВА
# ══════════════════════════════════════════════
SPAM_WORDS = [
    "казино", "ставки", "крипт", "форекс", "заработай за 1 день",
    "схема заработка", "реферальн", "mlm", "сетевой маркетинг",
    "100% доход", "без вложений", "пассивный доход", "бинар",
    "карточки маркетплейс", "карточки озон", "карточки вайлдберриз",
    "карточки wildberries", "карточки ozon", "инфобизнес курс продать",
]

FRAUD_WORDS = [
    "после сдачи оплачу", "оплата по факту", "тестовое задание бесплатно",
    "доверяю на слово", "предоплата не нужна", "сначала работа потом деньги",
    "готов платить после", "оплата после проверки",
]

QUALITY_WORDS = [
    "техническое задание", "тз", "требования", "нужно", "требуется",
    "ищем", "задача", "срок", "deadline", "дедлайн", "бюджет",
    "опыт", "портфолио", "примеры работ",
]

LONGTERM_WORDS = [
    "долгосрочн", "постоянн", "регулярн", "на постоянной основе",
    "долгое сотрудничество", "тестовый заказ", "первый заказ из серии",
    "возможно продолжение", "дальнейшее сотрудничество",
]

BUDGET_RE = re.compile(r"(\d[\d\s]{1,6})\s*(руб|₽|rub|тыс\.?|к\b|k\b)", re.IGNORECASE)
RESPONSES_RE = re.compile(r"(\d+)\s*(отклик|ответ|предложени)", re.IGNORECASE)

# ══════════════════════════════════════════════
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ══════════════════════════════════════════════

def moscow_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=TZ_OFFSET)))

def is_quiet_time() -> bool:
    h = moscow_now().hour
    if QUIET_START > QUIET_END:
        return h >= QUIET_START or h < QUIET_END
    return QUIET_START <= h < QUIET_END

def is_morning() -> bool:
    h = moscow_now().hour
    return h == QUIET_END  # ровно 8:00

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

def extract_budget(text: str) -> tuple[str, int]:
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
    """Скоринг заказа от 0 до 10. Чем выше — тем лучше."""
    score = 0
    tl = order["text"].lower()

    # Бюджет
    b = order["budget_num"]
    if b >= 30000:   score += 4
    elif b >= 15000: score += 3
    elif b >= 10000: score += 2
    elif b >= 5000:  score += 1

    # Конкретное ТЗ
    if any(w in tl for w in QUALITY_WORDS):
        score += 1

    # Низкая конкуренция в нише
    if order["niche"] in LOW_COMPETITION_NICHES:
        score += 2

    # Долгосрок
    if order["longterm"]:
        score += 2

    # Мало откликов
    r = order["responses"]
    if r == 0:    score += 1
    elif r <= 10: score += 1

    # Длинный текст = подробное ТЗ
    if len(order["text"]) > 300:
        score += 1

    return score

async def fetch_channel(session: aiohttp.ClientSession, channel: str) -> list[dict]:
    url = f"https://t.me/s/{channel}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    posts = []
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as r:
            if r.status != 200:
                log.warning(f"{channel}: HTTP {r.status}")
                return posts
            html = await r.text()
        blocks = re.findall(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
        ids    = re.findall(r'data-post="[^/]+/(\d+)"', html)
        for i, block in enumerate(blocks):
            text = re.sub(r"<br\s*/?>", "\n", block)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"[ \t]+", " ", text).strip()
            text = (text.replace("&amp;","&").replace("&lt;","<")
                       .replace("&gt;",">").replace("&#34;",'"').replace("&nbsp;"," "))
            pid = ids[i] if i < len(ids) else f"p{i}"
            posts.append({"id": f"{channel}_{pid}", "text": text, "channel": channel})
    except asyncio.TimeoutError:
        log.warning(f"{channel}: timeout")
    except Exception as e:
        log.warning(f"{channel}: {e}")
    return posts

async def send_tg(session: aiohttp.ClientSession, text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    # Telegram лимит 4096 символов
    if len(text) > 4000:
        text = text[:3990] + "\n…(обрезано)"
    payload = {"chat_id": OWNER_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status != 200:
                log.warning(f"sendMessage {r.status}: {await r.text()}")
    except Exception as e:
        log.warning(f"sendMessage error: {e}")

# ══════════════════════════════════════════════
#  СБОРКА СООБЩЕНИЙ
# ══════════════════════════════════════════════

def format_order(order: dict, index: int) -> str:
    preview = order["text"][:220].replace("\n", " ")
    if len(order["text"]) > 220:
        preview += "…"
    reply   = REPLIES.get(order["niche"], "Готов взяться за вашу задачу. Уточните детали?")
    flags   = []
    if order["longterm"]:   flags.append("🔁 долгосрок")
    if order["responses"] == 0: flags.append("👤 0 откликов")
    elif order["responses"] <= 10: flags.append(f"👤 {order['responses']} откл.")
    if order["niche"] in LOW_COMPETITION_NICHES: flags.append("🎯 низкая конкуренция")
    flag_str = "  ".join(flags)

    return (
        f"<b>{index}. {order['niche']}</b>  •  @{order['channel']}\n"
        f"💰 {order['budget_str']}   ⭐ скор: {order['score']}/10"
        + (f"\n{flag_str}" if flag_str else "") +
        f"\n\n{preview}\n\n"
        f"✍️ <i>{reply}</i>\n"
    )

def build_digest(orders: list[dict], top_n: int, title: str) -> list[str]:
    """Возвращает список сообщений (может быть несколько если много заказов)."""
    top = sorted(orders, key=lambda x: x["score"], reverse=True)[:top_n]
    if not top:
        return []

    messages = []
    header = f"📋 <b>{title}</b>\nНайдено: <b>{len(orders)}</b>  •  Показываю топ <b>{len(top)}</b>\n\n"
    current = header
    sep = "─" * 30 + "\n"

    for i, o in enumerate(top, 1):
        block = sep + format_order(o, i)
        if len(current) + len(block) > 3800:
            messages.append(current)
            current = f"📋 <b>{title}</b> (продолжение)\n\n" + block
        else:
            current += block

    messages.append(current)
    return messages

def format_urgent(order: dict) -> str:
    preview = order["text"][:300].replace("\n", " ")
    if len(order["text"]) > 300:
        preview += "…"
    reply = REPLIES.get(order["niche"], "Готов взяться за вашу задачу. Уточните детали?")
    tag = "🔥 СРОЧНО — высокий бюджет" if order["budget_num"] >= URGENT_BUDGET else "🔁 СРОЧНО — долгосрочное сотрудничество"
    return (
        f"{tag}\n\n"
        f"<b>{order['niche']}</b>  •  @{order['channel']}\n"
        f"💰 {order['budget_str']}   ⭐ скор: {order['score']}/10\n\n"
        f"{preview}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✍️ <b>Готовый отклик:</b>\n<i>{reply}</i>"
    )

# ══════════════════════════════════════════════
#  СБОР ЗАКАЗОВ
# ══════════════════════════════════════════════

async def collect_orders(session: aiohttp.ClientSession, seen: set) -> list[dict]:
    orders = []
    for channel in CHANNELS:
        posts = await fetch_channel(session, channel)
        for post in posts:
            if post["id"] in seen:
                continue
            seen.add(post["id"])

            text = post["text"]
            if len(text) < MIN_TEXT_LEN:   continue
            if is_spam(text):              continue
            if is_fraud(text):             continue

            niche = detect_niche(text)
            if not niche:                  continue

            budget_str, budget_num = extract_budget(text)
            if budget_num == 0:            continue   # без бюджета не берём
            if budget_num < MIN_BUDGET:    continue

            responses = extract_responses(text)
            if responses > MAX_RESPONSES:  continue

            longterm = is_longterm(text)
            order = {
                "niche":       niche,
                "channel":     channel,
                "text":        text,
                "budget_str":  budget_str,
                "budget_num":  budget_num,
                "responses":   responses,
                "longterm":    longterm,
                "id":          post["id"],
            }
            order["score"] = score_order(order)
            if order["score"] < MIN_SCORE: continue

            orders.append(order)
        await asyncio.sleep(2)
    return orders

# ══════════════════════════════════════════════
#  ГЛАВНЫЙ ЦИКЛ
# ══════════════════════════════════════════════

async def main():
    seen = load_seen()
    pending: list[dict] = []   # накопленные заказы между дайджестами
    last_digest = moscow_now()
    morning_sent_date = None   # чтобы утренний дайджест слать только раз

    log.info(f"Старт. Видено ранее: {len(seen)} постов.")

    async with aiohttp.ClientSession() as session:
        await send_tg(session,
            "✅ <b>Freelance Monitor v3 запущен!</b>\n\n"
            f"🔍 Каналов: <b>{len(CHANNELS)}</b>\n"
            f"💰 Минимальный бюджет: <b>{MIN_BUDGET:,} ₽</b>\n".replace(",", " ") +
            f"🔥 Срочные уведомления: от <b>{URGENT_BUDGET:,} ₽</b> или долгосрок\n".replace(",", " ") +
            f"📬 Дайджест каждые <b>2 часа</b>, утром в <b>08:00</b> за ночь\n"
            f"🌙 Тихие часы: <b>21:00–08:00</b>\n\n"
            "Слежу за заказами 👀"
        )

        while True:
            now = moscow_now()
            log.info(f"Сбор заказов... {now.strftime('%H:%M')}")

            new_orders = await collect_orders(session, seen)
            save_seen(seen)
            log.info(f"Новых подходящих: {len(new_orders)}")

            # Срочные уведомления — слать сразу даже ночью
            for o in new_orders:
                if o["budget_num"] >= URGENT_BUDGET or o["longterm"]:
                    await send_tg(session, format_urgent(o))
                    await asyncio.sleep(1)
                else:
                    pending.append(o)

            # Утренний дайджест в 8:00
            if now.hour == QUIET_END and morning_sent_date != now.date():
                morning_sent_date = now.date()
                if pending:
                    msgs = build_digest(pending, DIGEST_TOP_NIGHT,
                                        f"Доброе утро! Заказы за ночь 🌅")
                    for m in msgs:
                        await send_tg(session, m)
                        await asyncio.sleep(1)
                    pending.clear()
                else:
                    await send_tg(session, "🌅 Доброе утро! За ночь подходящих заказов не нашлось.")

            # Дневной дайджест каждые 2 часа (только не в тихое время)
            elif not is_quiet_time():
                elapsed = (now - last_digest).total_seconds()
                if elapsed >= DIGEST_INTERVAL:
                    last_digest = now
                    if len(pending) >= MIN_ORDERS_TO_SEND:
                        msgs = build_digest(pending, DIGEST_TOP_DAY,
                                            f"Дайджест {now.strftime('%H:%M')}")
                        for m in msgs:
                            await send_tg(session, m)
                            await asyncio.sleep(1)
                        pending.clear()
                    else:
                        log.info(f"Мало заказов ({len(pending)}), копим до следующего дайджеста.")

            await asyncio.sleep(600)  # проверяем каждые 10 минут

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Бот остановлен.")
