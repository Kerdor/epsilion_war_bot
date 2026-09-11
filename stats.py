import json
from pathlib import Path


class Stats:
    def __init__(self, account_number):
        self.path = Path("data") / f"account{account_number}.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self.data = {
            "level": 1,
            "battles": 0,
            "wins": 0,
            "losses": 0,
            "rewards": {},
            "stats_message_id": None,
        }

        self._load()

    def _load(self):
        if not self.path.exists():
            return

        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            self.data.update(saved)
        except (json.JSONDecodeError, OSError):
            pass

    def save(self):
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def set_level(self, level):
        self.data["level"] = level
        self.save()

    def add_battle(self, won):
        self.data["battles"] += 1
        self.data["wins" if won else "losses"] += 1
        self.save()

    def add_reward(self, name, amount):
        self.data["rewards"][name] = self.data["rewards"].get(name, 0) + amount
        self.save()

    def render(self):
        lines = [
            "⚔️ Epsilion War — статистика",
            f"🔸 Уровень: {self.data['level']}",
            "",
            f"Бои: {self.data['battles']}",
            f"Победы: {self.data['wins']}",
            f"Поражения: {self.data['losses']}",
            "",
            "🎁 Получено:",
        ]

        if self.data["rewards"]:
            for name, amount in self.data["rewards"].items():
                lines.append(f"{name}: {amount}")
        else:
            lines.append("—")

        return "\n".join(lines)
