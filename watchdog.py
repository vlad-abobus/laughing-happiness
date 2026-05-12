from __future__ import annotations

import os
import time

import requests

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("WATCHDOG_CHAT_ID", "")

last_status = "unknown"


def send(msg: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg},
            timeout=5,
        )
    except Exception:
        pass


def main() -> None:
    global last_status
    while True:
        try:
            r = requests.get("http://127.0.0.1:8080/ping", timeout=2)

            if r.status_code == 200:
                if last_status != "alive":
                    send("flurbursier online 🟢")
                    last_status = "alive"
            else:
                if last_status != "dead":
                    send("flurbursier offline 🔴")
                    last_status = "dead"

        except Exception:
            if last_status != "dead":
                send("flurbursier offline 🔴")
                last_status = "dead"

        time.sleep(30)


if __name__ == "__main__":
    main()
