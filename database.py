"""
База данных: записи долга и история.
"""
import os
import aiosqlite
from datetime import datetime
from pathlib import Path

_env_path = os.getenv("DEBT_BOT_DB_PATH")
DB_PATH = Path(_env_path) if _env_path else Path(__file__).parent / "debt.db"
if _env_path:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


async def init_db():
    """Создать таблицы."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usdt REAL NOT NULL,
                rub REAL NOT NULL,
                rate REAL NOT NULL,
                comment TEXT DEFAULT '',
                paid INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        # Миграция: добавить comment, если таблица создана до обновления
        try:
            await db.execute("ALTER TABLE records ADD COLUMN comment TEXT DEFAULT ''")
        except Exception:
            pass
        await db.commit()


async def add_record(usdt: float, rub: float, rate: float, comment: str = "") -> int:
    """Добавить запись. Возвращает id."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO records (usdt, rub, rate, comment, paid, created_at) VALUES (?, ?, ?, ?, 0, ?)",
            (usdt, rub, rate, comment or "", now),
        )
        await db.commit()
        return cursor.lastrowid


async def get_unpaid_records() -> list[dict]:
    """Список неоплаченных записей."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, usdt, rub, rate, COALESCE(comment, '') as comment, created_at FROM records WHERE paid = 0 ORDER BY id"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_total_debt_rub() -> float:
    """Итоговая сумма долга в рублях (только неоплаченные)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COALESCE(SUM(rub), 0) FROM records WHERE paid = 0"
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] or 0


async def mark_paid(record_id: int) -> bool:
    """Отметить запись как оплаченную (переместить в историю)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE records SET paid = 1 WHERE id = ? AND paid = 0",
            (record_id,),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_history() -> list[dict]:
    """История (оплаченные записи)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, usdt, rub, rate, COALESCE(comment, '') as comment, created_at FROM records WHERE paid = 1 ORDER BY id DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def delete_from_history(record_id: int) -> bool:
    """Удалить запись из истории."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM records WHERE id = ? AND paid = 1",
            (record_id,),
        )
        await db.commit()
        return cursor.rowcount > 0
