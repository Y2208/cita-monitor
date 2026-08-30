#!/usr/bin/env python3
import os
import re
import sys
import urllib.request
import urllib.parse
from datetime import datetime

from playwright.sync_api import sync_playwright

FIRST_URL = ("https://www.exteriores.gob.es/Consulados/lahabana/es/ServiciosConsulares/"
             "Paginas/index.aspx?scco=Cuba&scd=166&scca=Visados&scs=Visados+Nacionales+-+"
             "Visado+de+residencia+de+familiares+de+personas+de+nacionalidad+espa%c3%b1ola")

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


def click_if_present(pg, pattern, kind="button"):
    """Intenta hacer clic en un botón/enlace/texto que matchee el patrón. No falla si no existe."""
    try:
        if kind == "button":
            loc = pg.get_by_role("button", name=re.compile(pattern, re.I))
        elif kind == "link":
            loc = pg.get_by_role("link", name=re.compile(pattern, re.I))
        else:
            loc = pg.get_by_text(re.compile(pattern, re.I))
        if loc.count() > 0:
            loc.first.click(timeout=5000)
            pg.wait_for_timeout(2000)
            log(f"Clic hecho en: {pattern}")
            return True
    except Exception as e:
        log(f"No se pudo hacer clic en '{pattern}': {e}")
    return False


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
        current = page

        try:
            log("Paso 1: abriendo pagina oficial del consulado...")
            page.goto(FIRST_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            log("Paso 2: buscando enlace 'Reservar cita de visados RFX'...")
            link = page.get_by_text(re.compile("Reservar cita de visados RFX", re.I))
            if link.count() == 0:
                log("No se encontro el enlace esperado. Guardando estado y saliendo.")
                log(f"Titulo de la pagina: {page.title()}")
                browser.close()
                sys.exit(1)

            try:
                with context.expect_page(timeout=10000) as new_page_info:
                    link.first.click()
                current = new_page_info.value
                current.wait_for_load_state("domcontentloaded", timeout=30000)
                log("Se abrio una pestana nueva, cambiando a ella.")
            except Exception:
                log("No se abrio pestana nueva, seguimos en la misma pagina.")
                current = page

            current.wait_for_timeout(3000)

            log("Paso 3: buscando ventana emergente con boton 'Aceptar'...")
            click_if_present(current, "aceptar", kind="button")

            log("Paso 4: buscando pagina intermedia con boton 'Continuar'...")
            clicked = click_if_present(current, "continuar", kind="button")
            if not clicked:
                click_if_present(current, "continuar", kind="text")

            current.wait_for_timeout(4000)

            if "#services" not in current.url:
                log("Forzando navegacion a #services...")
                base = current.url.split("#")[0]
                current.goto(base + "#services", wait_until="domcontentloaded", timeout=30000)
                current.wait_for_timeout(6000)

            
          log(f"URL final alcanzada: {current.url}")

            all_text = current.content()
            for fr in current.frames:
                try:
                    all_text += " " + fr.content()
                except Exception as e:
                    log(f"No se pudo leer un frame: {e}")

            # Normaliza espacios raros (no separables, tabs, saltos) a espacio normal
            content = " ".join(all_text.lower().split())

            # Log de diagnostico: muestra un fragmento alrededor de "disponib"
            idx = content.find("disponib")
            if idx >= 0:
                log(f"Contexto encontrado: ...{content[max(0,idx-60):idx+60]}...")
            else:
                log("La palabra 'disponib' no aparece en el contenido leido.")

        except Exception as e:
            log(f"Error durante la navegacion: {e}")
            browser.close()
            sys.exit(1)

        if any(x in content for x in ["captcha", "acceso denegado", "are you a robot"]):
            log("El sitio pidio verificacion/bloqueo el acceso. No se insiste.")
            browser.close()
            return

        if any(phrase in content for phrase in NO_SLOTS_PHRASES):
            log("Sin citas disponibles por ahora.")
            browser.close()
            return

        log("Posible disponibilidad detectada!")
        current.screenshot(path="alerta.png", full_page=True)
        browser.close()
        send_telegram(f"Posible cita disponible.\nRevisa desde: {FIRST_URL}")


if __name__ == "__main__":
    main()