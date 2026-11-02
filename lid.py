import os
import sys
import subprocess
import tempfile
import asyncio
import socket

# =====================================================================
# 1. АВТОУСТАНОВКА БИБЛИОТЕК
# =====================================================================
def install_packages():
    print("Проверка и установка библиотек (при первом запуске может занять время)...")
    packages = ["aiogram", "google-generativeai", "edge-tts", "openai-whisper", "httpx[socks]"]
    for pkg in packages:
        try:
            if pkg == "httpx[socks]":
                __import__("socks")
            else:
                __import__(pkg.replace("-", "_"))
        except ImportError:
            print(f"Устанавливаем {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
    print("Все библиотеки на месте.")

install_packages()

# =====================================================================
# 2. НАСТРОЙКА ПРОКСИ (АВТОПОИСК)
# =====================================================================
def find_working_proxy():
    # Популярные порты локальных прокси (Clash, Nekoray, Outline, V2Ray и др.)
    ports = [1080, 10808, 7890, 7891, 10809, 2080]
    
    for port in ports:
        # Проверяем, открыт ли порт
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex(('127.0.0.1', port)) == 0:
                print(f"✅ Найден открытый порт: {port}. Используем его для прокси.")
                # Пробуем socks5 (чаще всего)
                return f'socks5://127.0.0.1:{port}'
    return None

proxy_url = find_working_proxy()

if proxy_url:
    os.environ['http_proxy'] = proxy_url
    os.environ['HTTP_PROXY'] = proxy_url
    os.environ['https_proxy'] = proxy_url
    os.environ['HTTPS_PROXY'] = proxy_url
    print(f"Установлен прокси: {proxy_url}")
else:
    print("⚠️ ВНИМАНИЕ: Не найдено ни одного локального прокси-порта!")
    print("Убедись, что VPN включен и в нем активирован 'Локальный прокси' (Local Proxy).")
    print("Если ошибка 400 User location не исчезнет, возможно, прокси работает на другом порту.")

import edge_tts
import google.generativeai as genai
import whisper
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile

# =====================================================================
# 3. НАСТРОЙКИ БОТА
# =====================================================================
BOT_TOKEN = "8863364376:AAEJgh6fI8WAg4aCqU0TcCUUByU1JB99ctE"
GEMINI_API_KEY = "AQ.Ab8RN6JXJ5F7Dp4XAJ6dAPUsRhukfAme7V83DTHfKoUawEuT3Q"

if BOT_TOKEN == "ВСТАВЬ_СЮДА_ТОКЕН_ОТ_BOTFATHER":
    print("ОШИБКА: Ты не вставил BOT_TOKEN в код!")
    sys.exit(1)

# Инициализация Gemini
genai.configure(api_key=GEMINI_API_KEY)

# ВАЖНО: Название модели. Если gemini-3.8-flash не работает, попробуй "gemini-1.5-flash"
MODEL_NAME = "gemini-2.5-flash" 
gemini_model = genai.GenerativeModel(MODEL_NAME)

print("Загрузка модели Whisper (может занять время при первом запуске)...")
whisper_model = whisper.load_model("small")
print("Модель Whisper загружена.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# =====================================================================
# 4. ФУНКЦИИ ОБРАБОТКИ
# =====================================================================
async def transcribe_voice(file_path: str) -> str:
    result = whisper_model.transcribe(file_path, language="ru")
    return result["text"].strip()

async def get_gemini_reply(text: str) -> str:
    prompt = f"Ты — мой личный ИИ-секретарь. Отвечай кратко, дружелюбно и по делу.\n\nПользователь: {text}"
    try:
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Ошибка Gemini: {e}\n(Проверь VPN и настройки прокси)"

async def text_to_voice_ogg(text: str) -> str:
    mp3_path = tempfile.mktemp(suffix=".mp3")
    ogg_path = tempfile.mktemp(suffix=".ogg")

    communicate = edge_tts.Communicate(text, "ru-RU-DmitryNeural")
    await communicate.save(mp3_path)

    # Если ffmpeg не установлен в системе, будет ошибка
    subprocess.run([
        "ffmpeg", "-y", "-i", mp3_path,
        "-acodec", "libopus", "-b:a", "48k",
        "-ar", "48000", "-ac", "1",
        ogg_path
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if os.path.exists(mp3_path):
        os.remove(mp3_path)
    return ogg_path

# =====================================================================
# 5. ОБРАБОТЧИКИ TELEGRAM
# =====================================================================
@dp.message(F.voice)
async def handle_voice(message: Message):
    await message.answer("🎤 Слушаю...")
    file = await bot.get_file(message.voice.file_id)
    ogg_input = tempfile.mktemp(suffix=".ogg")
    await bot.download_file(file.file_path, ogg_input)

    try:
        user_text = await transcribe_voice(ogg_input)
        await message.answer(f"🗣 *Вы сказали:*\n{user_text}", parse_mode="Markdown")

        reply_text = await get_gemini_reply(user_text)
        
        if len(reply_text) > 400:
            reply_text = reply_text[:400] + "..."
            
        await message.answer(f"🤖 *Ответ:*\n{reply_text}", parse_mode="Markdown")

        ogg_reply = await text_to_voice_ogg(reply_text)
        await message.answer_voice(FSInputFile(ogg_reply))
        os.remove(ogg_reply)
        
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
    finally:
        if os.path.exists(ogg_input):
            os.remove(ogg_input)

@dp.message(F.text)
async def handle_text(message: Message):
    await message.answer("✍️ Думаю...")
    reply_text = await get_gemini_reply(message.text)
    await message.answer(reply_text)

# =====================================================================
# 6. ЗАПУСК
# =====================================================================
async def main():
    print("Бот запущен! Иди в Телеграм.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())