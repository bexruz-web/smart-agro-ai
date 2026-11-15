"""Smart Agro AI Telegram boti (aiogram 3) — konsepsiya bo'yicha:
/start → til tanlash (UZB · RUS · ENG) → «Hududingizni tanlang» (Mini App). Bildirishnoma va ogohlantirishlarni backend yuboradi.
Rejim: BOT_MODE=polling (oddiy) yoki webhook (HTTPS kerak).
"""
import asyncio
import logging
import os
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, Message, WebAppInfo

from bot import api_client as api

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # URL'da bot tokeni bor
log = logging.getLogger("bot")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
MODE = os.getenv("BOT_MODE", "polling")
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")

TEXT = {
    "choose_lang": "Choose a language · Tilni tanlang · Выберите язык",
    "welcome": {
        "uz": "Assalomu alaykum! 🌾 Smart Agro AI — aqlli dehqonchilik yordamchisi.\n\nDalalaringizni qo'shish va kuzatish uchun hududingizni tanlang.",
        "ru": "Здравствуйте! 🌾 Smart Agro AI — умный помощник фермера.\n\nВыберите свой регион, чтобы добавить и отслеживать поля.",
        "en": "Hello! 🌾 Smart Agro AI is your smart farming assistant.\n\nChoose your region to add and monitor your fields.",
    },
    "region_btn": {"uz": "📍 Hududingizni tanlang", "ru": "📍 Выберите регион", "en": "📍 Choose your region"},
    "no_webapp": {
        "uz": "ℹ️ Mini App manzili (HTTPS domen) hali sozlanmagan — administrator WEBAPP_URL ni o'rnatishi kerak.",
        "ru": "ℹ️ Адрес Mini App (HTTPS-домен) ещё не настроен — администратору нужно указать WEBAPP_URL.",
        "en": "ℹ️ The Mini App address (HTTPS domain) is not configured yet — the admin needs to set WEBAPP_URL.",
    },
    "agronom_hint": {
        "uz": "AI Agronom har bir dalaning ichida ishlaydi: Mini App'ni oching va dalangizni tanlang.",
        "ru": "AI-агроном работает внутри каждого поля: откройте Mini App и выберите поле.",
        "en": "The AI Agronomist works inside each field: open the Mini App and pick your field.",
    },
    "lang_saved": {"uz": "Til: O'zbekcha ✅", "ru": "Язык: Русский ✅", "en": "Language: English ✅"},
}
LANG_BUTTONS = [("en", "🇬🇧 English"), ("uz", "🇺🇿 O'zbekcha"), ("ru", "🇷🇺 Русский")]

router = Router()


def webapp_ok() -> bool:
    """Mini App faqat haqiqiy HTTPS domenda ochiladi ("https://YANGI_DOMEN/" kabi to'ldirilmagan qiymat — yo'q deb olinadi)."""
    host = urlparse(WEBAPP_URL).hostname or ""
    return WEBAPP_URL.startswith("https://") and "." in host


def region_markup(lang: str) -> InlineKeyboardMarkup | None:
    if not webapp_ok():
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=TEXT["region_btn"][lang], web_app=WebAppInfo(url=WEBAPP_URL))]])


def lang_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=label, callback_data=f"lang:{code}")]
                                                 for code, label in LANG_BUTTONS])


async def farmer_lang(user) -> str:
    try:
        farmer = await api.upsert_farmer(user)
        return farmer.get("language") or "en"
    except api.ApiError as e:
        log.warning("upsert failed: %s", e.detail)
        return "en"


@router.message(CommandStart())
async def start(m: Message):
    await farmer_lang(m.from_user)
    await m.answer(TEXT["choose_lang"], reply_markup=lang_markup())


@router.callback_query(F.data.startswith("lang:"))
async def choose_lang(c: CallbackQuery):
    lang = c.data.split(":", 1)[1]
    if lang not in ("en", "uz", "ru"):
        await c.answer()
        return
    try:
        await api.set_language(c.from_user.id, lang)
    except api.ApiError as e:
        log.warning("set_language failed: %s", e.detail)
    await c.answer(TEXT["lang_saved"][lang])
    if c.message:
        try:
            await c.message.edit_text(TEXT["lang_saved"][lang])
        except Exception:  # noqa: BLE001 — eski xabarni tahrirlab bo'lmasligi mumkin
            pass
        markup = region_markup(lang)
        text = TEXT["welcome"][lang] + ("" if markup else "\n\n" + TEXT["no_webapp"][lang])
        await c.message.answer(text, reply_markup=markup)


@router.message(F.text)
async def any_text(m: Message):
    lang = await farmer_lang(m.from_user)
    markup = region_markup(lang)
    await m.answer(TEXT["agronom_hint"][lang] + ("" if markup else "\n\n" + TEXT["no_webapp"][lang]), reply_markup=markup)


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
    dp = Dispatcher()
    dp.include_router(router)
    dp.startup.register(on_startup)
    if MODE == "webhook" and webapp_ok():
        from aiohttp import web
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

        async def run_webhook():
            webhook_url = WEBAPP_URL.rstrip("/") + "/tg/webhook"
            await bot.set_webhook(webhook_url, secret_token=WEBHOOK_SECRET or None)
            log.info("Webhook o'rnatildi: %s", webhook_url)
            wapp = web.Application()
            SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET or None).register(
                wapp, path="/tg/webhook"
            )
            setup_application(wapp, dp, bot=bot)
            runner = web.AppRunner(wapp)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", 8081)
            await site.start()
            log.info("Webhook serveri 0.0.0.0:8081 portida ishlamoqda")
            # Davomiy ishlash uchun siqilmasdan kutish
            try:
                await asyncio.Event().wait()
            finally:
                await runner.cleanup()

        asyncio.run(run_webhook())
    else:
        async def run():
            await bot.delete_webhook(drop_pending_updates=False)
            await dp.start_polling(bot)

        asyncio.run(run())


if __name__ == "__main__":
    main()
