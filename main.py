import os
import logging
from aiohttp import web
from music_bot import bot, dp

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO)

async def handle_webhook(request):
    data = await request.json()
    await dp.feed_raw_update(bot, data)
    return web.Response()

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"✅ Webhook установлен: {WEBHOOK_URL}")

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()

def start_web_app():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    start_web_app()
