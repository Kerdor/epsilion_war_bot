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
        self.level_up_pending = False
        self.health_check_task = None

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
        self.stop_health_check()
        self.in_battle = False
        self.waiting_for_health = True
        await self.send("/start")
        print(f"[Аккаунт {self.number}] Проверяем здоровье перед запуском игры")

        if not self.health_check_task or self.health_check_task.done():
            self.health_check_task = asyncio.create_task(self._health_check_loop())

    async def start_health_check(self):
        if self.health_check_task and not self.health_check_task.done():
            return

        self.waiting_for_health = True
        self.health_check_task = asyncio.create_task(self._health_check_loop())

    async def _health_check_loop(self):
        while self.waiting_for_health and not self.in_battle:
            await asyncio.sleep(60)

            if not self.waiting_for_health or self.in_battle:
                return

            try:
                print(f"[Аккаунт {self.number}] Проверка HP")
                await self.send("/start")
            except Exception as error:
                print(f"[Аккаунт {self.number}] Ошибка проверки HP: {error}")

    def stop_health_check(self):
        self.waiting_for_health = False

        if self.health_check_task and not self.health_check_task.done():
            self.health_check_task.cancel()

        self.health_check_task = None

    def get_reply_buttons(self, event):
        markup = event.message.reply_markup
        if not markup:
            return []

        buttons = []
        for row in markup.rows:
            for button in row.buttons:
                if getattr(button, "text", None):
                    buttons.append(button.text)

        return buttons

    async def choose_block(self, event):
        buttons = self.get_reply_buttons(event)
        available = [button for button in buttons if button != "Сбежать"]

        # С щитом варианты защиты содержат 3 части тела.
        shield_blocks = [
            button for button in available
            if len(button.split(",")) == 3
        ]

        # Без щита варианты защиты содержат 2 части тела.
        normal_blocks = [
            button for button in available
            if len(button.split(",")) == 2
        ]

        if len(shield_blocks) == 5:
            block = random.choice(shield_blocks)
            print(f"[Аккаунт {self.number}] Щит: выбираем защиту: {block}")
        elif len(normal_blocks) == 5:
            block = random.choice(normal_blocks)
            print(f"[Аккаунт {self.number}] Обычная защита: {block}")
        else:
            print(f"[Аккаунт {self.number}] Неизвестная клавиатура защиты: {available}")
            return

        await self.send(block)

    async def on_game_message(self, event):
        text = event.raw_text.strip()
        lower = text.lower()

        print(f"[Аккаунт {self.number}] {text[:120].replace(chr(10), ' | ')}")

        if "недостаточно здоровья для сражений" in lower:
            self.in_battle = False
            self.processing_reward = False
            await self.start_health_check()
            return

        level_up_match = re.search(r"получил\s+(\d+)\s+.*?уровень", lower)
        if level_up_match:
            self.stats.set_level(int(level_up_match.group(1)))
            self.level_up_pending = True
            await self.update_stats_message()
            return

        if "начался поиск противника" in lower:
            return

        if "куда будешь бить?" in lower:
            self.stop_health_check()
            self.in_battle = True
            await self.send(random.choice(ATTACKS))
            return

        if "что будешь блокировать?" in lower:
            await self.choose_block(event)
            return

        if "ожидаем завершения хода" in lower:
            return

        # В некоторых боях сообщение с вопросом о первом ударе не приходит.
        # После результата хода выбираем удар для следующего хода.
        if re.search(r"ход\s+\d+", lower):
            self.stop_health_check()
            self.in_battle = True
            print(f"[Аккаунт {self.number}] Выбираем удар для следующего хода")
            await self.send(random.choice(ATTACKS))
            return

        if "ты победил своего врага" in lower:
            self.in_battle = False
            self.processing_reward = True
            self.stats.add_battle(won=True)
            self._parse_rewards(text)
            await self.update_stats_message()
            await self.send("✅ Забрать награду")

            if self.level_up_pending:
                self.level_up_pending = False
                self.processing_reward = False
                await self.send("⚔️ Найти врагов")
            else:
                await self.start_health_check()
            return

        if any(word in lower for word in ("ты проиграл", "поражение", "проиграл")):
            self.stop_health_check()
            self.in_battle = False
            self.processing_reward = False
            self.level_up_pending = False
            self.stats.add_battle(won=False)
            await self.update_stats_message()
            await self.send("⚔️ Найти врагов")
            return

        if "ваше здоровье полностью восстановлено" in lower:
            self.stop_health_check()
            self.processing_reward = False
            await self.send("⚔️ Найти врагов")
            return

        if self.waiting_for_health:
            level_match = re.search(r"🔸\s*(\d+)", text)
            hp_match = re.search(r"❤️\s*\(\s*(\d+)\s*/\s*(\d+)\s*\)", text)

            if level_match and hp_match:
                level = int(level_match.group(1))
                current_hp = int(hp_match.group(1))
                max_hp = int(hp_match.group(2))

                if self.stats.data["level"] != level:
                    self.stats.set_level(level)
                    await self.update_stats_message()

                print(f"[Аккаунт {self.number}] HP: {current_hp}/{max_hp}, уровень: {level}")

                if current_hp >= max_hp:
                    self.stop_health_check()
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
    accounts = [
        account
        for account in ACCOUNTS
        if account.get("phone") and account.get("session_name")
    ]

    print(f"Настроено аккаунтов: {len(accounts)}")

    account_bots = [AccountBot(account) for account in accounts]

    for account in account_bots:
        await account.connect()

    print("Все аккаунты подключены. Проверяем здоровье перед запуском.")

    await asyncio.gather(*(account.start_game() for account in account_bots))
    print(f"Запущено аккаунтов: {len(account_bots)}")

    await asyncio.gather(
        *(account.client.run_until_disconnected() for account in account_bots)
    )


if __name__ == "__main__":
    asyncio.run(main())
