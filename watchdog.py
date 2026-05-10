import requests
import time

BOT_TOKEN = ""
CHAT_ID = ""

last_status = "unknown"

def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg},
            timeout=5
        )
    except:
        pass


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

    except:
        if last_status != "dead":
            send("flurbursier offline 🔴")
            last_status = "dead"

    time.sleep(30)
