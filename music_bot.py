import logging
import os
import asyncio
import json
import yt_dlp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

# === НАСТРОЙКИ ===
API_TOKEN = os.getenv("API_TOKEN")  # токен бота из Render
MAX_FILE_SIZE_MB = 50
CACHE_DIR = "cache"
COOKIES_FILE = "cookies.txt"
TRACKS_FILE = "tracks.json"

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # например: https://telegram-music-bot-d9oz.onrender.com
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

os.makedirs(CACHE_DIR, exist_ok=True)

# === ЗАГРУЗКА/СОХРАНЕНИЕ ПЛЕЙЛИСТОВ ===
def load_tracks():
    if os.path.exists(TRACKS_FILE):
        try:
            with open(TRACKS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_tracks():
    with open(TRACKS_FILE, "w", encoding="utf-8") as f:
        json.dump(user_tracks, f, ensure_ascii=False, indent=2)

user_tracks = load_tracks()

# === СОСТОЯНИЯ ===
class SearchStates(StatesGroup):
    waiting_for_search = State()

# === КНОПКИ ===
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔍 Найти трек")],
        [KeyboardButton(text="🎼 Моя музыка")],
        [KeyboardButton(text="ℹ️ О боте")]
    ],
    resize_keyboard=True
)

# === КОМАНДЫ ===
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply("🎵 Привет! Я музыкальный бот.\nВыбери действие:", reply_markup=main_menu)

@dp.message(F.text == "ℹ️ О боте")
async def about_bot(message: types.Message):
    await message.reply(
        "Я ищу треки на YouTube и отправляю их в mp3. "
        "А также в разделе «Моя музыка» будут все треки, которые ты скачивал.\n\n"
        "📌 Автор: @wtfguys4\n"
        "Выбери «🔍 Найти трек» и введи название."
    )

@dp.message(F.text == "🔍 Найти трек")
async def ask_track_name(message: types.Message, state: FSMContext):
    await message.reply("Напиши название песни, которую хочешь найти:")
    await state.set_state(SearchStates.waiting_for_search)

@dp.message(F.text == "🎼 Моя музыка")
async def my_music(message: types.Message):
    tracks = user_tracks.get(str(message.from_user.id), [])
    existing_tracks = [p for p in tracks if os.path.exists(p)]

    if len(existing_tracks) != len(tracks):
        user_tracks[str(message.from_user.id)] = existing_tracks
        save_tracks()

    if not existing_tracks:
        return await message.reply("📂 У тебя пока нет сохранённых треков.")

    await message.reply(f"🎧 Отправляю твои треки ({len(existing_tracks)} шт.) порциями...")

    batch_size = 10
    for i in range(0, len(existing_tracks), batch_size):
        batch = existing_tracks[i:i + batch_size]
        for path in batch:
            try:
                await message.reply_audio(types.FSInputFile(path), title=os.path.basename(path))
                await asyncio.sleep(0.4)
            except Exception as e:
                await message.reply(f"⚠ Ошибка при отправке {os.path.basename(path)}: {e}")
        
        if i + batch_size < len(existing_tracks):
            await asyncio.sleep(2)

@dp.message(SearchStates.waiting_for_search, F.text)
async def search_music(message: types.Message, state: FSMContext):
    query = message.text.strip()
    await state.clear()
    await message.reply("🔍 Ищу треки...")

    try:
        with yt_dlp.YoutubeDL({
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'cookiefile': COOKIES_FILE
        }) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)
            results = info.get("entries", [])
            if not results:
                return await message.reply("❌ Ничего не нашёл.")

            keyboard = [
                [InlineKeyboardButton(text=video.get("title", "Без названия"), callback_data=f"dl:{video['id']}")]
                for video in results[:5]
            ]
            await message.reply("🎶 Выбери трек:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

    except Exception as e:
        await message.reply(f"❌ Ошибка при поиске: {e}")

@dp.callback_query(F.data.startswith("dl:"))
async def download_track(callback: types.CallbackQuery):
    video_id = callback.data.split(":")[1]
    url = f"https://www.youtube.com/watch?v={video_id}"
    await callback.message.edit_text("⏳ Скачиваю...")

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(CACHE_DIR, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192'
        }],
        'cookiefile': COOKIES_FILE
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = os.path.splitext(ydl.prepare_filename(info))[0] + ".mp3"

        size_mb = os.path.getsize(filename) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            os.remove(filename)
            return await callback.message.edit_text(f"❌ Файл слишком большой ({size_mb:.1f} МБ).")

        user_tracks.setdefault(str(callback.from_user.id), []).append(filename)
        save_tracks()

        await callback.message.edit_text("✅ Трек добавлен в твой плейлист 🎼 (см. 'Моя музыка')")

    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка при скачивании: {e}")

# === WEBHOOK ДЛЯ RENDER ===
async def handle_webhook(request):
    try:
        data = await request.json()
        update = types.Update(**data)
        await dp.feed_update(bot, update)
    except Exception as e:
        logging.error(f"Webhook handling error: {e}")
    return web.Response(text="ok")

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook set to {WEBHOOK_URL}")

async def on_shutdown(app):
    await bot.delete_webhook()

def start_web_app():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    port = int(os.getenv("PORT", 8080))
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    start_web_app()
