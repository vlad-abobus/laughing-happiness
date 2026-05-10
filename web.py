from flask import Flask, request, jsonify, render_template_string
import sqlite3

app = Flask(__name__)

conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()


# -------------------------
# UI (простая панель)
# -------------------------
HTML = """
<!DOCTYPE html>
<html>
<head>
<title>DB CONTROL PANEL</title>
<style>
body { background:#0f0f0f; color:white; font-family:Arial; padding:20px; }
input, button { padding:10px; margin:5px; }
table { width:100%; margin-top:20px; border-collapse:collapse; }
td,th { border:1px solid #444; padding:8px; }
</style>
</head>
<body>

<h2>Bot Database Control</h2>

<input id="uid" placeholder="user_id">
<button onclick="block()">Block</button>
<button onclick="unblock()">Unblock</button>

<button onclick="load()">Refresh</button>

<table id="table"></table>

<script>
async function block(){
 let id=document.getElementById("uid").value;
 await fetch("/block",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_id:id})});
 load();
}

async function unblock(){
 let id=document.getElementById("uid").value;
 await fetch("/unblock",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_id:id})});
 load();
}

async function load(){
 let r=await fetch("/db");
 let d=await r.json();

 let t="<tr><th>User ID</th></tr>";
 d.forEach(x=>t+=`<tr><td>${x[0]}</td></tr>`);

 document.getElementById("table").innerHTML=t;
}

load();
</script>

</body>
</html>
"""


# -------------------------
# PAGE
# -------------------------
@app.route("/")
def home():
    return render_template_string(HTML)


# -------------------------
# GET DB
# -------------------------
@app.route("/db")
def db():
    cursor.execute("SELECT * FROM blocked_users")
    return jsonify(cursor.fetchall())


# -------------------------
# BLOCK USER
# -------------------------
@app.route("/block", methods=["POST"])
def block():
    user_id = request.json["user_id"]

    cursor.execute("""
        INSERT OR IGNORE INTO blocked_users (user_id)
        VALUES (?)
    """, (user_id,))
    conn.commit()

    return {"ok": True}


# -------------------------
# UNBLOCK USER
# -------------------------
@app.route("/unblock", methods=["POST"])
def unblock():
    user_id = request.json["user_id"]

    cursor.execute("""
        DELETE FROM blocked_users
        WHERE user_id = ?
    """, (user_id,))
    conn.commit()

    return {"ok": True}


# -------------------------
# RUN SERVER
# -------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
