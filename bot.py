"""
Telegram-бот для учёта долгов (USDT → RUB).
"""
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import BOT_TOKEN, ALLOWED_USER_IDS, PROXY
from database import (
    init_db,
    add_record,
    get_unpaid_records,
    get_total_debt_rub,
    mark_paid,
    get_history,
    delete_from_history,
)
from rate_parser import get_usdt_to_rub_rate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _create_bot() -> Bot:
    if PROXY:
        from aiogram.client.session.aiohttp import AiohttpSession
        session = AiohttpSession(proxy=PROXY)
        return Bot(token=BOT_TOKEN, session=session)
    return Bot(token=BOT_TOKEN)


bot = _create_bot()
router = Router()


def check_access(user_id: int) -> bool:
    """Проверка белого списка."""
    if not ALLOWED_USER_IDS:
        return True  # Если список пуст — разрешить всем (для первой настройки)
    return user_id in ALLOWED_USER_IDS


async def access_denied(message: Message):
    await message.answer("⛔ Доступ запрещён. Ваш ID не в белом списке.")


# --- FSM ---
class AddRecord(StatesGroup):
    wait_usdt = State()
    wait_comment = State()
    confirm = State()


# --- Форматирование ---
def fmt_sum(v: float) -> str:
    return f"{v:,.2f}".replace(",", " ").replace(".", ",")


def _fmt_comment(s: str) -> str:
    """Безопасное отображение комментария (экранирование Markdown)."""
    if not s:
        return ""
    return s.replace("\\", "\\\\").replace("`", "\\`").replace("_", "\\_").replace("*", "\\*")


async def _safe_edit(message, text, **kwargs):
    """edit_text с игнорированием ошибки «сообщение не изменилось»."""
    try:
        await message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


# --- Handlers ---


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if not check_access(message.from_user.id):
        await access_denied(message)
        return

    await state.clear()
    debt = await get_total_debt_rub()
    text = (
        f"💰 *Общая сумма долга: {fmt_sum(debt)} ₽*\n\n"
        "Выберите действие:"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="📋 Список долгов", callback_data="list")
    kb.button(text="➕ Добавить запись", callback_data="add")
    kb.button(text="📜 История", callback_data="history")
    kb.adjust(1)
    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="Markdown")


@router.callback_query(F.data == "menu")
async def cb_menu(cb: CallbackQuery, state: FSMContext):
    if not check_access(cb.from_user.id):
        await cb.answer("⛔ Доступ запрещён")
        return

    await state.clear()
    debt = await get_total_debt_rub()
    text = (
        f"💰 *Общая сумма долга: {fmt_sum(debt)} ₽*\n\n"
        "Выберите действие:"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="📋 Список долгов", callback_data="list")
    kb.button(text="➕ Добавить запись", callback_data="add")
    kb.button(text="📜 История", callback_data="history")
    kb.adjust(1)
    await _safe_edit(cb.message, text, reply_markup=kb.as_markup(), parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data == "list")
async def cb_list(cb: CallbackQuery):
    if not check_access(cb.from_user.id):
        await cb.answer("⛔ Доступ запрещён")
        return

    records = await get_unpaid_records()
    debt = await get_total_debt_rub()

    if not records:
        text = f"💰 *Долг: {fmt_sum(debt)} ₽*\n\nЗаписей пока нет."
        kb = InlineKeyboardBuilder()
        kb.button(text="◀ В меню", callback_data="menu")
        await _safe_edit(cb.message, text, reply_markup=kb.as_markup(), parse_mode="Markdown")
        await cb.answer()
        return

    lines = [f"💰 *Общий долг: {fmt_sum(debt)} ₽*\n"]
    kb = InlineKeyboardBuilder()
    for r in records:
        line = f"• #{r['id']} | {fmt_sum(r['usdt'])} USDT = {fmt_sum(r['rub'])} ₽ (курс {r['rate']})"
        if r.get("comment"):
            line += f"\n  _{_fmt_comment(r['comment'])}_"
        lines.append(line)
        kb.button(text=f"✓ Оплачено #{r['id']}", callback_data=f"pay_{r['id']}")
    kb.button(text="◀ В меню", callback_data="menu")
    kb.adjust(1)

    await _safe_edit(cb.message, "\n".join(lines), reply_markup=kb.as_markup(), parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data.startswith("pay_"))
async def cb_pay(cb: CallbackQuery):
    if not check_access(cb.from_user.id):
        await cb.answer("⛔ Доступ запрещён")
        return

    rid = int(cb.data.split("_")[1])
    ok = await mark_paid(rid)
    if ok:
        await cb.answer("✅ Запись отмечена оплаченной")
        # Обновляем список (без повторного answer)
        records = await get_unpaid_records()
        debt = await get_total_debt_rub()
        if not records:
            text = f"💰 *Долг: {fmt_sum(debt)} ₽*\n\nВсе записи оплачены."
            kb = InlineKeyboardBuilder()
            kb.button(text="◀ В меню", callback_data="menu")
        else:
            lines = [f"💰 *Общий долг: {fmt_sum(debt)} ₽*\n"]
            kb = InlineKeyboardBuilder()
            for r in records:
                line = f"• #{r['id']} | {fmt_sum(r['usdt'])} USDT = {fmt_sum(r['rub'])} ₽ (курс {r['rate']})"
                if r.get("comment"):
                    line += f"\n  _{_fmt_comment(r['comment'])}_"
                lines.append(line)
                kb.button(text=f"✓ Оплачено #{r['id']}", callback_data=f"pay_{r['id']}")
            kb.button(text="◀ В меню", callback_data="menu")
            text = "\n".join(lines)
        kb.adjust(1)
        await _safe_edit(cb.message, text, reply_markup=kb.as_markup(), parse_mode="Markdown")
    else:
        await cb.answer("❌ Запись не найдена или уже оплачена")


@router.callback_query(F.data == "add")
async def cb_add_start(cb: CallbackQuery, state: FSMContext):
    if not check_access(cb.from_user.id):
        await cb.answer("⛔ Доступ запрещён")
        return

    await state.set_state(AddRecord.wait_usdt)
    await _safe_edit(cb.message, "Введите сумму в USDT (например: 50 или 123.45):")
    await cb.answer()


@router.message(AddRecord.wait_usdt, F.text)
async def add_usdt_input(message: Message, state: FSMContext):
    if not check_access(message.from_user.id):
        return

    text = message.text.replace(",", ".").replace(" ", "")
    try:
        usdt = float(text)
        if usdt <= 0:
            await message.answer("Введите положительное число.")
            return
    except ValueError:
        await message.answer("Неверный формат. Введите число, например: 50")
        return

    await message.answer("⏳ Получаю курс с CoinMarketCap...")
    rate = await get_usdt_to_rub_rate()
    if rate is None:
        await message.answer(
            "Не удалось получить курс. Введите сумму в рублях вручную "
            "(или попробуйте позже):"
        )
        await state.update_data(usdt=usdt, rate=None)
        await state.set_state(AddRecord.confirm)
        return

    rub = round(usdt * rate, 2)
    await state.update_data(usdt=usdt, rub=rub, rate=rate)
    await state.set_state(AddRecord.wait_comment)

    kb = InlineKeyboardBuilder()
    kb.button(text="⏭ Пропустить", callback_data="add_skip_comment")
    kb.button(text="❌ Отмена", callback_data="menu")
    kb.adjust(1)

    await message.answer(
        f"📊 *Курс:* 1 USDT = {rate} ₽\n"
        f"📊 *Сумма:* {fmt_sum(usdt)} USDT = *{fmt_sum(rub)} ₽*\n\n"
        "Комментарий (необязательно). Напишите текст или нажмите «Пропустить»:",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )


@router.callback_query(AddRecord.wait_comment, F.data == "add_skip_comment")
async def cb_add_skip_comment(cb: CallbackQuery, state: FSMContext):
    """Пропуск комментария — переход к подтверждению."""
    if not check_access(cb.from_user.id):
        await cb.answer("⛔ Доступ запрещён")
        return

    await state.update_data(comment="")
    await _show_add_confirm(cb.message, state, can_edit=True)
    await cb.answer()


@router.message(AddRecord.wait_comment, F.text)
async def add_comment_input(message: Message, state: FSMContext):
    """Ввод комментария."""
    if not check_access(message.from_user.id):
        return

    comment = (message.text or "").strip()[:500]  # Ограничение длины
    await state.update_data(comment=comment)
    await _show_add_confirm(message, state, can_edit=False)


def _format_record_preview(data: dict) -> str:
    """Форматирование превью записи для подтверждения."""
    usdt = data["usdt"]
    rub = data.get("rub") or 0
    rate = data.get("rate") or (rub / usdt if usdt else 0)
    comment = data.get("comment") or ""
    text = (
        f"📊 *Курс:* 1 USDT = {rate} ₽\n"
        f"📊 *Сумма:* {fmt_sum(usdt)} USDT = *{fmt_sum(rub)} ₽*"
    )
    if comment:
        text += f"\n📝 *Комментарий:* {_fmt_comment(comment)}"
    text += "\n\nПодтвердить добавление?"
    return text


async def _show_add_confirm(target, state: FSMContext, can_edit: bool = True):
    """
    Показать экран подтверждения добавления записи.
    can_edit=False — когда target это сообщение пользователя (нельзя редактировать).
    """
    data = await state.get_data()
    await state.set_state(AddRecord.confirm)
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Сохранить", callback_data="add_confirm")
    kb.button(text="❌ Отмена", callback_data="menu")
    kb.adjust(1)
    text = _format_record_preview(data)
    parse_mode = "Markdown"
    if can_edit:
        await _safe_edit(target, text, reply_markup=kb.as_markup(), parse_mode=parse_mode)
    else:
        await target.answer(text, reply_markup=kb.as_markup(), parse_mode=parse_mode)


@router.callback_query(AddRecord.confirm, F.data == "add_confirm")
async def cb_add_confirm(cb: CallbackQuery, state: FSMContext):
    if not check_access(cb.from_user.id):
        await cb.answer("⛔ Доступ запрещён")
        return

    data = await state.get_data()
    usdt = data["usdt"]
    rub = data.get("rub")
    rate = data.get("rate")
    comment = data.get("comment") or ""

    if rub is None:
        await cb.answer("Добавьте сумму в рублях через команду /add")
        await state.clear()
        return

    if rate is None:
        rate = rub / usdt if usdt else 0

    rid = await add_record(usdt, rub, rate, comment)
    await state.clear()
    await cb.answer(f"✅ Запись #{rid} добавлена")
    await cb_menu(cb, state)


@router.callback_query(F.data == "history")
async def cb_history(cb: CallbackQuery):
    if not check_access(cb.from_user.id):
        await cb.answer("⛔ Доступ запрещён")
        return

    records = await get_history()

    if not records:
        text = "История пуста."
        kb = InlineKeyboardBuilder()
        kb.button(text="◀ В меню", callback_data="menu")
        await _safe_edit(cb.message, text, reply_markup=kb.as_markup())
        await cb.answer()
        return

    lines = ["📜 *История (оплаченные записи):*\n"]
    kb = InlineKeyboardBuilder()
    for r in records:
        line = f"• #{r['id']} | {fmt_sum(r['usdt'])} USDT = {fmt_sum(r['rub'])} ₽"
        if r.get("comment"):
            line += f"\n  _{_fmt_comment(r['comment'])}_"
        lines.append(line)
        kb.button(text=f"🗑 Удалить #{r['id']}", callback_data=f"del_{r['id']}")
    kb.button(text="◀ В меню", callback_data="menu")
    kb.adjust(1)

    await _safe_edit(cb.message, "\n".join(lines), reply_markup=kb.as_markup(), parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data.startswith("del_"))
async def cb_delete(cb: CallbackQuery):
    if not check_access(cb.from_user.id):
        await cb.answer("⛔ Доступ запрещён")
        return

    rid = int(cb.data.split("_")[1])
    ok = await delete_from_history(rid)
    if ok:
        await cb.answer("✅ Запись удалена")
        records = await get_history()
        kb = InlineKeyboardBuilder()
        if not records:
            text = "История пуста."
        else:
            lines = ["📜 *История (оплаченные записи):*\n"]
            for r in records:
                line = f"• #{r['id']} | {fmt_sum(r['usdt'])} USDT = {fmt_sum(r['rub'])} ₽"
                if r.get("comment"):
                    line += f"\n  _{_fmt_comment(r['comment'])}_"
                lines.append(line)
                kb.button(text=f"🗑 Удалить #{r['id']}", callback_data=f"del_{r['id']}")
            text = "\n".join(lines)
        kb.button(text="◀ В меню", callback_data="menu")
        kb.adjust(1)
        await _safe_edit(cb.message, text, reply_markup=kb.as_markup(), parse_mode="Markdown")
    else:
        await cb.answer("❌ Запись не найдена")


@router.message(AddRecord.confirm, F.text)
async def add_manual_rub(message: Message, state: FSMContext):
    """Ручной ввод рублёвой суммы, если курс не получен."""
    if not check_access(message.from_user.id):
        return

    data = await state.get_data()
    if data.get("rub") is not None:
        return  # Уже есть рублёвая сумма

    text = message.text.replace(",", ".").replace(" ", "")
    try:
        rub = float(text)
        if rub <= 0:
            await message.answer("Введите положительное число.")
            return
    except ValueError:
        await message.answer("Неверный формат. Введите число в рублях.")
        return

    usdt = data["usdt"]
    rate = rub / usdt if usdt else 0
    await state.update_data(rub=rub, rate=rate)
    await state.set_state(AddRecord.wait_comment)

    kb = InlineKeyboardBuilder()
    kb.button(text="⏭ Пропустить", callback_data="add_skip_comment")
    kb.button(text="❌ Отмена", callback_data="menu")
    kb.adjust(1)

    await message.answer(
        f"📊 *Сумма:* {fmt_sum(usdt)} USDT = *{fmt_sum(rub)} ₽*\n\n"
        "Комментарий (необязательно). Напишите текст или нажмите «Пропустить»:",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )


async def main():
    await init_db()
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
