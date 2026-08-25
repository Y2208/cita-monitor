#!/usr/bin/env python3
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime

from playwright.sync_api import sync_playwright

URL = "https://www.citaconsular.es/es/hosteds/widgetdefault/2686d3b68dc9e0db0ba3c6a20437e9cc7/#services"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

NO_SLOTS_PHRASES = [
    "no hay citas disponibles",
    "no existen horas disponibles",
    "actualmente no hay",
    "no hay horas",
]


def log(msg: str):
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}")


def send_telegram(msg: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("Telegram no configurado (faltan variables de entorno).")
        return
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": msg}).encode()
    try:
        urllib.request.urlopen(api_url, data=data, timeout=10)
        log("Notificacion enviada a Telegram.")
    except Exception as e:
        log(f"Error enviando Telegram: {e}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            locale="es-ES",
        )
        page = context.new_page()

        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(8000)
            content = page.content().lower()
        except Exception as e:
            log(f"Error al cargar la pagina: {e}")
            browser.close()
            sys.exit(1)

        browser.close()

        if any(x in content for x in ["captcha", "acceso denegado", "are you a robot", "cloudflare"]):
            log("El sitio pidio verificacion/bloqueo el acceso. No se insiste.")
            return

        if any(phrase in content for phrase in NO_SLOTS_PHRASES):
            log("Sin citas disponibles por ahora.")
            return

        log("Posible disponibilidad detectada!")
        send_telegram(f"Posible cita disponible en citaconsular.es.\nEntra a revisar: {URL}")


if __name__ == "__main__":
    main()
