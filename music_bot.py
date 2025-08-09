import logging
import os
import asyncio
import json
import yt_dlp
import browser_cookie3
from http.cookiejar import MozillaCookieJar
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

API_TOKEN = os.getenv("BOT_TOKEN")  # ⚡ токен из переменных окружения Render
MAX_FILE_SIZE_MB = 50
CACHE_DIR = "cache"
COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")
TRACKS_FILE = os.path.join(os.path.dirname(__file__), "tracks.json")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

os.makedirs(CACHE_DIR, exist_ok=True)

def export_cookies():
    try:
        cj = browser_cookie3.chrome(domain_name=".youtube.com")
        cj_mozilla = MozillaCookieJar()
        for cookie in cj:
            cj_mozilla.set_cookie(cookie)
        cj_mozilla.save(COOKIES_FILE, ignore_discard=True, ignore_expires=True)
        logging.info(f"✅ Cookies экспортированы в {COOKIES_FILE}")
    except Exception as e:
        logging.error(f"❌ Не удалось экспортировать cookies: {e}")

export_cookies()

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

class SearchStates(StatesGroup):
    waiting_for_search = State()

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔍 Найти трек")],
        [KeyboardButton(text="🎼 Моя музыка")],
        [KeyboardButton(text="ℹ️ О боте")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply("🎵 Привет! Я музыкальный бот.\nВыбери действие:", reply_markup=main_menu)

@dp.message(F.text == "ℹ️ О боте")
async def about_bot(message: types.Message):
    await message.reply("Я ищу треки на YouTube и отправляю их в mp3.")

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
    await message.reply(f"🎧 Отправляю твои треки ({len(existing_tracks)} шт.)...")
    for path in existing_tracks:
        try:
            await message.reply_audio(types.FSInputFile(path), title=os.path.basename(path))
            await asyncio.sleep(0.4)
        except Exception as e:
            await message.reply(f"⚠ Ошибка при отправке {os.path.basename(path)}: {e}")

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
        await callback.message.reply_audio(types.FSInputFile(filename), title=info.get("title"))
        await callback.message.edit_text("✅ Готово! Трек добавлен в твой плейлист 🎼")
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка при скачивании: {e}")
