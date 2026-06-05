name: Freelance Bot

on:
  schedule:
    # Дневной дайджест каждые 2 часа с 8:00 до 21:00 МСК (UTC+3)
    # В UTC это 5:00 до 18:00
    - cron: '0 5 * * *'   # 08:00 МСК
    - cron: '0 7 * * *'   # 10:00 МСК
    - cron: '0 9 * * *'   # 12:00 МСК
    - cron: '0 11 * * *'  # 14:00 МСК
    - cron: '0 13 * * *'  # 16:00 МСК
    - cron: '0 15 * * *'  # 18:00 МСК
    - cron: '0 17 * * *'  # 20:00 МСК
  workflow_dispatch:       # Можно запустить вручную

jobs:
  run-bot:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install aiohttp

      - name: Run bot
        run: python bot.py
        timeout-minutes: 10
