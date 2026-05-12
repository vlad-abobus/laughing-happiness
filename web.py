from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)


def _db_path() -> Path:
    return Path(os.getenv("DATABASE_PATH", "bot.db"))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Bot DB Panel</title>
<style>
body { background:#0f0f0f; color:white; font-family:Arial; padding:20px; }
input, button { padding:10px; margin:5px; }
table { width:100%; margin-top:20px; border-collapse:collapse; }
td,th { border:1px solid #444; padding:8px; font-size: 13px; }
h3 { margin-top: 28px; }
</style>
</head>
<body>

<h2>SQLite overview</h2>
<p>Файл БД: <code>{{ db_path }}</code></p>

<h3>Глобальные блокировки бота (AI)</h3>
<table id="blocked"></table>

<h3>Баны в чатах</h3>
<table id="bans"></table>

<h3>Последние нарушения</h3>
<table id="violations"></table>

<h3>Последние действия админов</h3>
<table id="audit"></table>

<button onclick="load()">Refresh</button>

<script>
async function load(){
  let r = await fetch("/api/overview");
  let d = await r.json();

  function tableFromRows(rows, columns){
    if(!rows.length) return "<tr><td>(пусто)</td></tr>";
    let h = "<tr>" + columns.map(c=>`<th>${c}</th>`).join("") + "</tr>";
    for(const row of rows){
      h += "<tr>" + columns.map(c=>`<td>${row[c] ?? ""}</td>`).join("") + "</tr>";
    }
    return h;
  }

  document.getElementById("blocked").innerHTML = tableFromRows(d.blocked, ["user_id","reason","created_at"]);
  document.getElementById("bans").innerHTML = tableFromRows(d.bans, ["chat_id","user_id","reason","created_at"]);
  document.getElementById("violations").innerHTML = tableFromRows(d.violations, ["id","chat_id","user_id","violation_type","detail","message_id","created_at"]);
  document.getElementById("audit").innerHTML = tableFromRows(d.audit, ["id","created_at","chat_id","admin_id","action","target_user_id","detail"]);
}

load();
</script>

</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(HTML, db_path=str(_db_path()))


@app.route("/api/overview")
def overview():
    conn = _connect()
    cur = conn.cursor()

    def fetchall(query: str) -> list[dict[str, object]]:
        cur.execute(query)
        rows = cur.fetchall()
        return [dict(r) for r in rows]

    blocked = fetchall("SELECT user_id, reason, created_at FROM global_bot_blocks ORDER BY created_at DESC LIMIT 200")
    bans = fetchall("SELECT chat_id, user_id, reason, created_at FROM chat_bans ORDER BY created_at DESC LIMIT 200")
    violations = fetchall(
        "SELECT id, chat_id, user_id, violation_type, detail, message_id, created_at "
        "FROM violations ORDER BY created_at DESC LIMIT 200"
    )
    audit = fetchall(
        "SELECT id, created_at, chat_id, admin_id, action, target_user_id, detail "
        "FROM admin_audit ORDER BY created_at DESC LIMIT 200"
    )
    conn.close()
    return jsonify(blocked=blocked, bans=bans, violations=violations, audit=audit)


@app.route("/block", methods=["POST"])
def block():
    user_id = int(request.json["user_id"])
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO global_bot_blocks(user_id, reason, created_at) VALUES(?, ?, ?)",
        (user_id, "web_panel", time.time()),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@app.route("/unblock", methods=["POST"])
def unblock():
    user_id = int(request.json["user_id"])
    conn = _connect()
    conn.execute("DELETE FROM global_bot_blocks WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
