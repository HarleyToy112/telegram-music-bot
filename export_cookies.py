import browser_cookie3
import os

# === Путь к cookies.txt ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.txt")

def export_cookies():
    try:
        cj = browser_cookie3.chrome(domain_name=".youtube.com")
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            for cookie in cj:
                f.write(
                    f"{cookie.domain}\tTRUE\t{cookie.path}\t"
                    f"{'TRUE' if cookie.secure else 'FALSE'}\t"
                    f"{int(cookie.expires) if cookie.expires else 0}\t"
                    f"{cookie.name}\t{cookie.value}\n"
                )
        print(f"✅ Cookies успешно выгружены в {COOKIES_FILE}")
    except Exception as e:
        print(f"⚠ Не удалось выгрузить cookies автоматически: {e}")
        print("💡 Обнови cookies.txt вручную через расширение Get cookies.txt LOCALLY")

# Вызываем при старте
export_cookies()