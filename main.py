import asyncio
import random
import re

from telethon import TelegramClient, events

from config import ACCOUNTS, API_HASH, API_ID, BOT_USERNAME
from stats import Stats

ATTACKS = [
    "В голову",
    "В грудь",
    "В живот",
    "В пояс",
    "В ноги",
]

BLOCKS = [
    "Голова, грудь",
    "Грудь, живот",
    "Живот, пояс",
    "Пояс, ноги",
    "Ноги, голова",
]


class AccountBot:
    def __init__(self, account):
        self.number = account["number"]
        self.phone = account["phone"]
        self.session_name = account["session_name"]
        self.client = TelegramClient(self.session_name, API_ID, API_HASH)
        self.stats = Stats(self.number)

        self.in_battle = False
        self.waiting_for_health = False
        self.processing_reward = False

        self.client.add_event_handler(
            self.on_game_message,
            events.NewMessage(from_users=BOT_USERNAME),
        )

    async def send(self, text):
        await self.client.send_message(BOT_USERNAME, text)

    async def update_stats_message(self):
        text = self.stats.render()
        message_id = self.stats.data.get("stats_message_id")

        if message_id:
            try:
                await self.client.edit_message("me", message_id, text)
                return
            except Exception:
                self.stats.data["stats_message_id"] = None

        message = await self.client.send_message("me", text)
        self.stats.data["stats_message_id"] = message.id
        self.stats.save()

    async def connect(self):
        await self.client.start(phone=self.phone)
        me = await self.client.get_me()
        print(f"[Аккаунт {self.number}] Авторизован: {me.first_name} (@{me.username})")
        await self.update_stats_message()

    async def start_game(self):
        await self.send("⚔️ Найти врагов")
        print(f"[Аккаунт {self.number}] Игра запущена")

    async def on_game_message(self, event):
        text = event.raw_text.strip()
        lower = text.lower()

        print(f"[Аккаунт {self.number}] {text[:120].replace(chr(10), ' | ') }")

        if "начался поиск противника" in lower:
            return

        if "куда будешь бить?" in lower:
            self.in_battle = True
            await self.send(random.choice(ATTACKS))
            return

        if "что будешь блокировать?" in lower:
            await self.send(random.choice(BLOCKS))
            return

        if "ожидаем завершения хода" in lower:
            await self.send(random.choice(ATTACKS))
            return

        if "ты победил своего врага" in lower:
            self.in_battle = False
            self.processing_reward = True
            self.stats.add_battle(won=True)
            self._parse_rewards(text)
            await self.update_stats_message()
            await self.send("✅ Забрать награду")
            return

        if any(word in lower for word in ("ты проиграл", "поражение", "проиграл")):
            self.in_battle = False
            self.processing_reward = False
            self.stats.add_battle(won=False)
            await self.update_stats_message()
            await self.send("⚔️ Найти врагов")
            return

        if "ваше здоровье полностью восстановлено" in lower:
            self.waiting_for_health = False
            self.processing_reward = False
            await self.send("⚔️ Найти врагов")
            return

    def _parse_rewards(self, text):
        if "получено в награду" not in text.lower():
            return

        for line in text.splitlines():
            match = re.search(r"^(.+?):\s*([0-9]+(?:[.,][0-9]+)?)$", line.strip())
            if not match:
                continue

            name = match.group(1).strip()
            amount = match.group(2).replace(",", ".")

            try:
                value = float(amount) if "." in amount else int(amount)
            except ValueError:
                continue

            self.stats.add_reward(name, value)


async def main():
    accounts = [AccountBot(account) for account in ACCOUNTS]

    print(f"Настроено аккаунтов: {len(accounts)}")

    # Подключаем аккаунты строго по очереди.
    # Уже подключённый аккаунт ничего не запускает и ждёт остальные.
    for account in accounts:
        await account.connect()

    print("Все аккаунты подключены. Запускаем игру.")

    # Только после подключения всех аккаунтов начинаем игру одновременно.
    await asyncio.gather(*(account.start_game() for account in accounts))
    print(f"Запущено аккаунтов: {len(accounts)}")

    await asyncio.gather(*(account.client.run_until_disconnected() for account in accounts))


if __name__ == "__main__":
    asyncio.run(main())
