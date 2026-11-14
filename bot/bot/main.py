"""Smart Agro AI Telegram boti (aiogram 3). Rejim: BOT_MODE=polling (oddiy) yoki webhook (HTTPS kerak)."""
import asyncio
import html
import logging
import os
from datetime import date

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonWebApp,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
)

from bot import api_client as api

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # URL'da bot tokeni bor
log = logging.getLogger("bot")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
MODE = os.getenv("BOT_MODE", "polling")
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
ACTION_UZ = {"done": "✅ Bajarildi", "later": "⏰ Keyinroq", "rejected": "❌ Kerak emas", "useful": "👍 Foydali", "not_useful": "👎 Foydasiz"}
QUALITIES = ["a'lo", "yaxshi", "o'rta", "past"]

router = Router()


def webapp_ok() -> bool:
    """Mini App faqat haqiqiy HTTPS domenda ochiladi ("https://YANGI_DOMEN/" kabi to'ldirilmagan qiymat — yo'q deb olinadi)."""
    from urllib.parse import urlparse

    host = urlparse(WEBAPP_URL).hostname or ""
    return WEBAPP_URL.startswith("https://") and "." in host


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="📍 Joylashuvni yuborish", request_location=True), KeyboardButton(text="📊 Hisobot")],
        [KeyboardButton(text="🌾 Hosilni kiritish"), KeyboardButton(text="❓ Yordam")],
    ])


def open_app_markup(path: str = "") -> InlineKeyboardMarkup | None:
    if not webapp_ok():
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🌱 Smart Agro AI'ni ochish",
                                                                       web_app=WebAppInfo(url=WEBAPP_URL + path))]])


HELP = (
    "<b>Smart Agro AI</b> — dalangiz uchun aqlli yordamchi.\n\n"
    "• Mini App'da dalangizni xaritada belgilang (4 burchak yoki polygon).\n"
    "• Tizim NASA POWER, ob-havo prognozi va sensorlaringiz ma'lumotlarini tahlil qiladi.\n"
    "• Har 4 soatda hisobot, muhim holatda darhol ogohlantirish keladi.\n"
    "• Tavsiyalar ostidagi tugmalar bilan javob bering — tizim sizning dalangizni o'rganadi.\n\n"
    "Buyruqlar: /hisobot — hozirgi hisobot, /hosil — hosil natijasini kiritish, /maydonlar — dalalar, "
    "/ochirish — ma'lumotlarimni o'chirish.\n"
    "Istalgan agronomik savolni shu yerga yozing — AI agronom javob beradi."
)


@router.message(CommandStart())
async def start(m: Message):
    try:
        await api.upsert_farmer(m.from_user)
    except api.ApiError as e:
        log.warning("upsert failed: %s", e.detail)
    text = (f"Assalomu alaykum, {m.from_user.first_name or 'fermer'}! 🌾\n\n" + HELP)
    await m.answer(text, reply_markup=main_keyboard())
    markup = open_app_markup()
    if markup:
        await m.answer("Dalangizni belgilash va tahlilni ko'rish uchun ilovani oching:", reply_markup=markup)
    else:
        await m.answer("ℹ️ Mini App manzili (WEBAPP_URL, https) hali sozlanmagan — administratorga murojaat qiling.")


@router.message(Command("yordam"))
@router.message(F.text == "❓ Yordam")
async def help_(m: Message):
    await m.answer(HELP, reply_markup=open_app_markup())


@router.message(F.location)
async def location(m: Message):
    try:
        await api.set_location(m.from_user.id, m.location.latitude, m.location.longitude)
        await m.answer("📍 Xo'jalik joylashuvi saqlandi. Endi Mini App'da dalangizni xaritada belgilang.",
                       reply_markup=open_app_markup())
    except api.ApiError as e:
        await m.answer(f"Joylashuvni saqlab bo'lmadi: {e.detail}. Avval /start bosing.")


@router.message(Command("hisobot"))
@router.message(F.text == "📊 Hisobot")
async def report(m: Message):
    try:
        res = await api.report(m.from_user.id)
    except api.ApiError as e:
        await m.answer(f"Hisobot tayyorlab bo'lmadi: {e.detail}")
        return
    if res.get("queued"):
        await m.answer(f"⏳ {res['queued']} ta dala bo'yicha hisobot tayyorlanmoqda — bir necha soniyada keladi.")
    else:
        await m.answer("Hali dala qo'shilmagan. Mini App'da dalangizni belgilang.", reply_markup=open_app_markup())


@router.message(Command("maydonlar"))
async def list_fields(m: Message):
    try:
        fields = await api.fields(m.from_user.id)
    except api.ApiError as e:
        await m.answer(e.detail)
        return
    if not fields:
        await m.answer("Hali dala qo'shilmagan.", reply_markup=open_app_markup())
        return
    lines = [f"• <b>{f['name']}</b> — {f['area_ha']} ga, {f['crop_name_uz'] or 'ekin kiritilmagan'}" for f in fields]
    await m.answer("Dalalaringiz:\n" + "\n".join(lines), reply_markup=open_app_markup())


# ---------------- Tavsiya tugmalari (FEEDBACK)
@router.callback_query(F.data.startswith("rec:"))
async def rec_feedback(c: CallbackQuery):
    try:
        _, rec_id, action = c.data.split(":")
        await api.feedback(c.from_user.id, int(rec_id), action)
    except (ValueError, api.ApiError) as e:
        await c.answer(f"Saqlab bo'lmadi: {getattr(e, 'detail', e)}", show_alert=True)
        return
    await c.answer(f"Qabul qilindi: {ACTION_UZ.get(action, action)}")
    if action in ("done", "later", "rejected") and c.message:
        rows = [[InlineKeyboardButton(text=f"Javobingiz: {ACTION_UZ[action]}", callback_data="noop")]]
        kb = c.message.reply_markup.inline_keyboard if c.message.reply_markup else []
        rows += [row for row in kb if any(b.web_app for b in row)]
        try:
            await c.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        except Exception:  # noqa: BLE001 — eski xabarni tahrirlab bo'lmasligi mumkin
            pass


@router.callback_query(F.data == "noop")
async def noop(c: CallbackQuery):
    await c.answer()


# ---------------- Hosil so'rovnomasi (ROT-1)
class Harvest(StatesGroup):
    field = State()
    yield_ = State()
    quality = State()
    water = State()
    fertilizers = State()
    problems = State()


def _skip_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[[KeyboardButton(text="⏭ O'tkazib yuborish")]])


def _num(text: str) -> float | None:
    try:
        return float(text.replace(",", ".").strip())
    except (ValueError, AttributeError):
        return None


@router.message(Command("hosil"))
@router.message(F.text == "🌾 Hosilni kiritish")
async def harvest_start(m: Message, state: FSMContext):
    try:
        fields = await api.fields(m.from_user.id)
    except api.ApiError as e:
        await m.answer(e.detail)
        return
    fields = [f for f in fields if f["crop"]]
    if not fields:
        await m.answer("Ekin ko'rsatilgan dala yo'q. Mini App'da dalangizga ekin kiriting.", reply_markup=open_app_markup())
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{f['name']} ({f['crop_name_uz']})",
                                                                      callback_data=f"hv:{f['id']}")] for f in fields])
    await state.set_state(Harvest.field)
    await m.answer("Qaysi dala bo'yicha hosil natijasini kiritamiz?", reply_markup=kb)


@router.callback_query(Harvest.field, F.data.startswith("hv:"))
async def harvest_field(c: CallbackQuery, state: FSMContext):
    await state.update_data(field_id=int(c.data.split(":")[1]))
    await state.set_state(Harvest.yield_)
    await c.answer()
    await c.message.answer("1/5. Qancha hosil olindi? Gektariga tonnada yozing (masalan: 4.8)")


@router.message(Harvest.yield_)
async def harvest_yield(m: Message, state: FSMContext):
    v = _num(m.text)
    if v is None or not (0 <= v <= 200):
        await m.answer("Iltimos, son kiriting (t/ga), masalan: 4.8")
        return
    await state.update_data(yield_t_ha=v)
    await state.set_state(Harvest.quality)
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[[KeyboardButton(text=q) for q in QUALITIES]])
    await m.answer("2/5. Hosil sifati qanday bo'ldi?", reply_markup=kb)


@router.message(Harvest.quality)
async def harvest_quality(m: Message, state: FSMContext):
    if m.text not in QUALITIES:
        await m.answer("Tugmalardan birini tanlang: " + ", ".join(QUALITIES))
        return
    await state.update_data(quality=m.text)
    await state.set_state(Harvest.water)
    await m.answer("3/5. Mavsumda qancha suv sarflandi? (jami m³; bilmasangiz — o'tkazib yuboring)", reply_markup=_skip_kb())


@router.message(Harvest.water)
async def harvest_water(m: Message, state: FSMContext):
    v = None if m.text.startswith("⏭") else _num(m.text)
    if v is None and not m.text.startswith("⏭"):
        await m.answer("Son kiriting (m³) yoki o'tkazib yuboring.")
        return
    await state.update_data(water_used_m3=v)
    await state.set_state(Harvest.fertilizers)
    await m.answer("4/5. Qanday o'g'itlar ishlatildi? (masalan: karbamid 200 kg/ga, ammofos 100 kg/ga)", reply_markup=_skip_kb())


@router.message(Harvest.fertilizers)
async def harvest_fert(m: Message, state: FSMContext):
    await state.update_data(fertilizers=None if m.text.startswith("⏭") else m.text[:2000])
    await state.set_state(Harvest.problems)
    await m.answer("5/5. Qanday muammolar yuzaga keldi? (zararkunanda, suv tanqisligi, sovuq…)", reply_markup=_skip_kb())


@router.message(Harvest.problems)
async def harvest_done(m: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    payload = {"harvest_date": date.today().isoformat(), "yield_t_ha": data["yield_t_ha"], "quality": data["quality"],
               "water_used_m3": data.get("water_used_m3"), "fertilizers": data.get("fertilizers"),
               "problems": None if m.text.startswith("⏭") else m.text[:2000]}
    try:
        res = await api.harvest(m.from_user.id, data["field_id"], payload)
    except api.ApiError as e:
        await m.answer(f"Saqlab bo'lmadi: {e.detail}", reply_markup=main_keyboard())
        return
    lines = [f"✅ Hosil saqlandi: <b>{res['yield_t_ha']} t/ga</b>."]
    if res.get("predicted_yield_t_ha"):
        diff = res["yield_t_ha"] - res["predicted_yield_t_ha"]
        lines.append(f"Tizim prognozi: {res['predicted_yield_t_ha']} t/ga (farq: {diff:+.2f} t/ga). Bu farq keyingi prognozlarni aniqlashtiradi.")
    if res.get("next_crops"):
        lines.append("\n🌱 <b>Keyingi mavsum uchun almashlab ekish tavsiyasi:</b>")
        for c in res["next_crops"]:
            y = c.get("yield") or {}
            lines.append(f"• {c['crop_name_uz']} — ball {c['score']}, kutilayotgan hosil {y.get('min_t_ha')}–{y.get('max_t_ha')} t/ga")
        lines.append("Batafsil (ballar, suv talabi, xavflar) — Mini App → Almashlab ekish.")
    await m.answer("\n".join(lines), reply_markup=main_keyboard())


# ---------------- Ma'lumotlarni o'chirish
@router.message(Command("ochirish"))
async def delete_ask(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Ha, hammasini o'chirish", callback_data="del:yes"),
                                                InlineKeyboardButton(text="Bekor qilish", callback_data="del:no")]])
    await m.answer("⚠️ Barcha dalalaringiz, sensor ma'lumotlari va tarix butunlay o'chiriladi. Bu amalni qaytarib bo'lmaydi. Davom etasizmi?",
                   reply_markup=kb)


@router.callback_query(F.data.startswith("del:"))
async def delete_do(c: CallbackQuery):
    if c.data == "del:yes":
        try:
            await api.delete_farmer(c.from_user.id)
            await c.message.edit_text("Ma'lumotlaringiz o'chirildi. Qayta boshlash uchun /start.")
        except api.ApiError as e:
            await c.message.edit_text(f"O'chirib bo'lmadi: {e.detail}")
    else:
        await c.message.edit_text("Bekor qilindi.")
    await c.answer()


# ---------------- AI agronom (erkin matn)
@router.message(F.text)
async def ai_chat(m: Message):
    await m.bot.send_chat_action(m.chat.id, "typing")
    try:
        res = await api.chat(m.from_user.id, m.text[:2000])
    except api.ApiError as e:
        if e.status == 404:
            await m.answer("Avval /start buyrug'ini bosing.")
        else:
            await m.answer("AI agronom hozir javob bera olmayapti, birozdan keyin urinib ko'ring.")
        return
    text = html.escape(res["reply"])[:3800]
    if res.get("sources"):
        text += "\n\n<i>Manbalar: " + html.escape(", ".join(res["sources"]))[:250] + "</i>"
    await m.answer(text)


async def on_startup(bot: Bot) -> None:
    if not webapp_ok():
        log.warning("WEBAPP_URL haqiqiy HTTPS manzil emas — Mini App tugmasi o'rnatilmadi (bot ishlashda davom etadi)")
        return
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Smart Agro AI", web_app=WebAppInfo(url=WEBAPP_URL)))
    except Exception as e:  # noqa: BLE001 — menyu tugmasi xatosi botni to'xtatmasligi kerak
        log.warning("Menyu tugmasini o'rnatib bo'lmadi: %s", e)


def main() -> None:
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN berilmagan (.env)")
    bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    dp.startup.register(on_startup)
    if MODE == "webhook":
        from aiohttp import web
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

        async def set_hook(bot_: Bot):
            await bot_.set_webhook(WEBAPP_URL.rstrip("/") + "/tg/webhook", secret_token=WEBHOOK_SECRET or None,
                                   drop_pending_updates=False)

        dp.startup.register(set_hook)
        app = web.Application()
        SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET or None).register(app, path="/tg/webhook")
        setup_application(app, dp, bot=bot)
        web.run_app(app, host="0.0.0.0", port=8081)
    else:
        async def run():
            await bot.delete_webhook(drop_pending_updates=False)
            await dp.start_polling(bot)

        asyncio.run(run())


if __name__ == "__main__":
    main()
