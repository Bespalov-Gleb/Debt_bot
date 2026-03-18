"""
База данных для новой логики:
- credit: внесение долга (приход)
- debit: погашение долга (расход), подтверждается фото чека
"""

import os
from datetime import datetime
from pathlib import Path

import aiosqlite

_env_path = os.getenv("DEBT_BOT_DB_PATH")
DB_PATH = Path(_env_path) if _env_path else Path(__file__).parent / "debt.db"
if _env_path:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS credits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount_input REAL NOT NULL,
                currency TEXT NOT NULL,
                amount_rub REAL NOT NULL,
                transfer_number TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS debits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_or_card TEXT NOT NULL,
                bank TEXT NOT NULL,
                amount_rub REAL NOT NULL,
                photo_file_id TEXT,
                created_at TEXT NOT NULL,
                confirmed INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        # Индексы под выборки pending/confirmed
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_debits_confirmed ON debits(confirmed, id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_credits_created_at ON credits(created_at, id)"
        )
        await db.commit()


async def add_credit(
    amount_input: float,
    currency: str,
    amount_rub: float,
    transfer_number: str,
) -> int:
    now = _now_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO credits (amount_input, currency, amount_rub, transfer_number, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (amount_input, currency, amount_rub, transfer_number, now),
        )
        await db.commit()
        return cursor.lastrowid


async def add_debit_request(phone_or_card: str, bank: str, amount_rub: float) -> int:
    now = _now_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO debits (phone_or_card, bank, amount_rub, photo_file_id, created_at, confirmed)
            VALUES (?, ?, ?, NULL, ?, 0)
            """,
            (phone_or_card, bank, amount_rub, now),
        )
        await db.commit()
        return cursor.lastrowid


async def confirm_debit(debit_id: int, photo_file_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE debits
            SET photo_file_id = ?, confirmed = 1
            WHERE id = ? AND confirmed = 0
            """,
            (photo_file_id, debit_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_credits() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, amount_input, currency, amount_rub, transfer_number, created_at FROM credits ORDER BY id"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_debits_pending(limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, phone_or_card, bank, amount_rub, created_at FROM debits WHERE confirmed = 0 ORDER BY id ASC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_debits_confirmed() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT id, phone_or_card, bank, amount_rub, photo_file_id, created_at
            FROM debits
            WHERE confirmed = 1
            ORDER BY id DESC
            """
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_total_credit_rub() -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COALESCE(SUM(amount_rub), 0) FROM credits") as cursor:
            row = await cursor.fetchone()
            return row[0] or 0


async def get_total_debit_confirmed_rub() -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COALESCE(SUM(amount_rub), 0) FROM debits WHERE confirmed = 1"
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] or 0


async def get_total_debt_rub() -> float:
    credit = await get_total_credit_rub()
    debit = await get_total_debit_confirmed_rub()
    return credit - debit
