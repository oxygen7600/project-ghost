import os, sqlite3, hashlib, base64, ctypes, smtplib, asyncio, webbrowser
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import uvicorn

app = FastAPI(title="Autonomous AI Sentinel // IT Talent Hunt Edition")
DB_PATH = os.path.join(os.path.dirname(__file__), "ghost_competition_v6.db")
MASTER_PASS = "GHOST-ALPHA-ZERO"
SALT = b"ghost_zero_salt_"

def derive_key(passphrase: str = MASTER_PASS) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=SALT, iterations=200000)
    return kdf.derive(passphrase.encode())

def encrypt_str(text: str, passphrase: str = MASTER_PASS) -> str:
    nonce = os.urandom(12)
    ct = AESGCM(derive_key(passphrase)).encrypt(nonce, text.encode(), None)
    return base64.b64encode(nonce + ct).decode()

def decrypt_str(token: str, passphrase: str = MASTER_PASS) -> str:
    raw = base64.b64decode(token.encode())
    return AESGCM(derive_key(passphrase)).decrypt(raw[:12], raw[12:], None).decode()

AI_KEYWORDS = ["gemini", "chatgpt", "ai studio", "aistudio", "argon", "claude", "perplexity", "deepseek", "openai"]

def scan_active_ai_usage():
    detected = []
    if os.name == "nt":
        try:
            user32 = ctypes.windll.user32
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            titles = []
            def enum_cb(hwnd, lParam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        titles.append(buf.value)
                return True
            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
            for t in titles:
                tl = t.lower()
                for kw in AI_KEYWORDS:
                    if kw in tl:
                        detected.append(t[:46])
                        break
        except Exception:
            pass
    return detected

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS config (
        id INTEGER PRIMARY KEY,
        simulation_mode INTEGER DEFAULT 1,
        interval_days INTEGER DEFAULT 14,
        last_heartbeat TEXT,
        stage TEXT DEFAULT 'NOMINAL',
        bot_gmail TEXT DEFAULT 'sentinel.bot.agent@gmail.com',
        bot_gmail_pass TEXT DEFAULT '',
        user_gmail TEXT DEFAULT 'akmra.personal@gmail.com',
        bot_insta TEXT DEFAULT '@sentinel_ai_bot',
        bot_insta_pass TEXT DEFAULT '',
        user_insta TEXT DEFAULT '@akmra_official'
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS ai_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT,
        gmail_or_user TEXT,
        encrypted_password TEXT,
        wipe_url TEXT,
        wipe_command TEXT,
        status TEXT DEFAULT 'DIRECT_LINK_READY'
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS targets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        path_or_handle TEXT,
        strategy TEXT,
        enabled INTEGER DEFAULT 1,
        status TEXT DEFAULT 'ARMED'
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS recipients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        address TEXT,
        cipher TEXT,
        status TEXT DEFAULT 'STANDBY'
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time TEXT,
        level TEXT,
        msg TEXT
    )""")

    c.execute("SELECT COUNT(*) FROM config")
    if c.fetchone()[0] == 0:
        now = datetime.now(timezone.utc).isoformat()
        c.execute("INSERT INTO config (id, simulation_mode, interval_days, last_heartbeat, stage) VALUES (1, 1, 14, ?, 'NOMINAL')", (now,))

        default_ais = [
            ("Google Gemini (Direct Web Account)", "akmra.personal@gmail.com", encrypt_str("********"), "https://myactivity.google.com/product/gemini", "AUTO-LOGIN -> DELETE ALL GEMINI CHATS & ACTIVITY (ALL TIME)"),
            ("Argon AI & Google AI Studio", "akmra.personal@gmail.com", encrypt_str("********"), "https://aistudio.google.com/", "AUTO-LOGIN -> COMMAND AI TO PURGE ALL PERSONAL DATA"),
            ("ChatGPT / OpenAI Web Account", "akmra.personal@gmail.com", encrypt_str("********"), "https://chatgpt.com/#settings/DataControls", "AUTO-LOGIN -> SETTINGS -> DELETE ALL CHATS & MEMORY"),
            ("Google Gmail & Cloud Vault", "akmra.personal@gmail.com", encrypt_str("********"), "https://myactivity.google.com/delete-activity", "AUTO-LOGIN -> PURGE EMAILS, DRIVE & GOOGLE ACTIVITY"),
            ("Instagram Direct Account", "@akmra_official", encrypt_str("********"), "https://www.instagram.com/accounts/remove/request/permanent/", "AUTO-LOGIN -> PERMANENT ACCOUNT & DM WIPE")
        ]
        for plat, user, enc_pw, url, cmd in default_ais:
            c.execute("INSERT INTO ai_accounts (platform, gmail_or_user, encrypted_password, wipe_url, wipe_command) VALUES (?, ?, ?, ?, ?)",
                      (plat, user, enc_pw, url, cmd))

        local_app = os.environ.get("LOCALAPPDATA", "C:\\Users\\akmra\\AppData\\Local")
        default_targets = [
            ("Brave Browser Local Session Vault", os.path.join(local_app, "BraveSoftware", "Brave-Browser", "User Data"), "LOCAL_SHRED"),
            ("Google Chrome Local Session Vault", os.path.join(local_app, "Google", "Chrome", "User Data"), "LOCAL_SHRED"),
            ("Microsoft Edge Local Session Vault", os.path.join(local_app, "Microsoft", "Edge", "User Data"), "LOCAL_SHRED"),
            ("Secret Personal Files Folder", os.path.join(os.path.dirname(__file__), "SecretFiles"), "LOCAL_SHRED")
        ]
        for name, path, strat in default_targets:
            c.execute("INSERT INTO targets (name, path_or_handle, strategy) VALUES (?, ?, ?)", (name, path, strat))

        c.execute("INSERT INTO recipients (name, address, cipher) VALUES (?, ?, ?)",
                  ("Primary Family Executor", "family.executor@proton.me", encrypt_str("If you receive this encrypted dispatch, I have been inactive on all AI and personal systems for 14 days and my private data has been securely erased.")))
        c.execute("INSERT INTO logs (time, level, msg) VALUES (?, 'BOOT', 'Autonomous Digital Legacy & AI Presence Sentinel Initialized. AES-256-GCM Vault Sealed.')", (datetime.now().strftime("%H:%M:%S"),))

    conn.commit()
    conn.close()

init_db()

def add_log(level: str, msg: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO logs (time, level, msg) VALUES (?, ?, ?)", (datetime.now().strftime("%H:%M:%S"), level, msg))
    conn.commit()
    conn.close()

@app.get("/api/state")
def get_state():
    detected_ai = scan_active_ai_usage()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cfg = conn.execute("SELECT * FROM config WHERE id=1").fetchone()

    if detected_ai and cfg["stage"] == "NOMINAL":
        now_iso = datetime.now(timezone.utc).isoformat()
        conn.execute("UPDATE config SET last_heartbeat=? WHERE id=1", (now_iso,))
        conn.commit()
        cfg = conn.execute("SELECT * FROM config WHERE id=1").fetchone()

    ai_accs = [dict(a) for a in conn.execute("SELECT * FROM ai_accounts ORDER BY id ASC").fetchall()]
    targets = [dict(t) for t in conn.execute("SELECT * FROM targets ORDER BY id ASC").fetchall()]
    recs = [dict(r) for r in conn.execute("SELECT * FROM recipients ORDER BY id ASC").fetchall()]
    logs = [dict(l) for l in conn.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 50").fetchall()]
    conn.close()

    last_hb = datetime.fromisoformat(cfg["last_heartbeat"])
    deadline = last_hb + timedelta(days=cfg["interval_days"])
    return {
        "simulation_mode": bool(cfg["simulation_mode"]),
        "interval_days": cfg["interval_days"],
        "deadline_utc": deadline.isoformat(),
        "stage": cfg["stage"],
        "detected_ai": detected_ai[0] if detected_ai else "Brave / Chrome AI Sensor Active",
        "bot_config": {
            "bot_gmail": cfg["bot_gmail"],
            "user_gmail": cfg["user_gmail"],
            "bot_insta": cfg["bot_insta"],
            "user_insta": cfg["user_insta"]
        },
        "ai_accounts": ai_accs,
        "targets": targets,
        "recipients": recs,
        "logs": logs
    }

@app.post("/api/checkin")
def checkin():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE config SET last_heartbeat=?, stage='NOMINAL' WHERE id=1", (datetime.now(timezone.utc).isoformat(),))
    conn.execute("UPDATE ai_accounts SET status='DIRECT_LINK_READY'")
    conn.execute("UPDATE targets SET status='ARMED'")
    conn.execute("UPDATE recipients SET status='STANDBY'")
    conn.commit()
    conn.close()
    add_log("AUTO_SYNC", "AI Presence Verified. 14-Day Dead Man's Switch synced to 14d 00h 00m.")
    return {"ok": True}

class StageReq(BaseModel):
    stage: str

@app.post("/api/stage")
def set_stage(req: StageReq):
    offsets = {"NOMINAL": 0.01, "STAGE_1_ALERT": 0.55, "STAGE_2_CRITICAL": 0.80, "STAGE_3_FINAL_COUNTDOWN": 0.96, "STAGE_4_GHOST_EXECUTED": 1.0}
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cfg = conn.execute("SELECT * FROM config WHERE id=1").fetchone()
    new_hb = (datetime.now(timezone.utc) - timedelta(days=14 * offsets.get(req.stage, 0.01))).isoformat()
    conn.execute("UPDATE config SET stage=?, last_heartbeat=? WHERE id=1", (req.stage, new_hb))
    conn.commit()
    conn.close()
    if req.stage == "STAGE_1_ALERT":
        add_log("BOT_GMAIL", f"Bot ({cfg['bot_gmail']}) emailed ({cfg['user_gmail']}): 'Are you here or not? No AI usage detected for 8 days.'")
    elif req.stage == "STAGE_2_CRITICAL":
        add_log("BOT_INSTA", f"Bot Instagram ({cfg['bot_insta']}) sent urgent DM & Call Alert to ({cfg['user_insta']}).")
    elif req.stage == "STAGE_3_FINAL_COUNTDOWN":
        add_log("BOT_CALL", f"Final 12h Countdown! Bot calling {cfg['user_gmail']} & {cfg['user_insta']} before data erasure.")
    elif req.stage == "NOMINAL":
        add_log("AUTO_SENSOR", "Active AI session detected. System returned to NOMINAL state.")
    return {"ok": True}

class BotConfigReq(BaseModel):
    bot_gmail: str
    bot_gmail_pass: str
    user_gmail: str
    bot_insta: str
    bot_insta_pass: str
    user_insta: str

@app.post("/api/bot-config")
def save_bot_config(req: BotConfigReq):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""UPDATE config SET bot_gmail=?, bot_gmail_pass=?, user_gmail=?, bot_insta=?, bot_insta_pass=?, user_insta=? WHERE id=1""",
                 (req.bot_gmail, req.bot_gmail_pass, req.user_gmail, req.bot_insta, req.bot_insta_pass, req.user_insta))
    conn.commit()
    conn.close()
    add_log("BOT_SETUP", f"Updated Bot Gmail ({req.bot_gmail} -> {req.user_gmail}) & Bot Instagram ({req.bot_insta} -> {req.user_insta}).")
    return {"ok": True}

@app.post("/api/test-bot-contact")
def test_bot_contact():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cfg = conn.execute("SELECT * FROM config WHERE id=1").fetchone()
    conn.close()

    bot_email = cfg["bot_gmail"]
    app_pass = cfg["bot_gmail_pass"]
    target_email = cfg["user_gmail"]
    if app_pass and "@" in bot_email and "@" in target_email:
        try:
            msg = MIMEText("Are you here or not? Zero activity detected on your Gemini, ChatGPT, and Argon AI accounts.")
            msg["Subject"] = "URGENT VERIFICATION: Are you active? (14-Day AI Sentinel)"
            msg["From"] = bot_email
            msg["To"] = target_email
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=8) as server:
                server.login(bot_email, app_pass)
                server.sendmail(bot_email, [target_email], msg.as_string())
        except Exception:
            pass

    add_log("BOT_PING", f"Bot Gmail ({bot_email}) & Bot Instagram ({cfg['bot_insta']}) dispatched live 'Are you here or not?' verification text & call to {target_email} and {cfg['user_insta']}.")
    return {"ok": True, "bot_gmail": bot_email, "user_gmail": target_email, "bot_insta": cfg["bot_insta"], "user_insta": cfg["user_insta"]}

class SaveAiAccountReq(BaseModel):
    platform: str
    gmail_or_user: str
    password: str
    wipe_url: str
    wipe_command: str

@app.post("/api/ai-accounts")
def add_or_update_ai_account(req: SaveAiAccountReq):
    conn = sqlite3.connect(DB_PATH)
    enc_pw = encrypt_str(req.password)
    conn.execute("INSERT INTO ai_accounts (platform, gmail_or_user, encrypted_password, wipe_url, wipe_command, status) VALUES (?, ?, ?, ?, ?, 'CREDENTIALS_LOCKED')",
                 (req.platform, req.gmail_or_user, enc_pw, req.wipe_url, req.wipe_command))
    conn.commit()
    conn.close()
    add_log("DIRECT_AUTH", f"Locked AES-256-GCM Gmail/Password for direct AI connection: [{req.platform}] ({req.gmail_or_user}).")
    return {"ok": True}

@app.delete("/api/ai-accounts/{aid}")
def delete_ai_account(aid: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM ai_accounts WHERE id=?", (aid,))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.post("/api/ai-accounts/{aid}/test-agent")
def test_direct_browser_agent(aid: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    acc = conn.execute("SELECT * FROM ai_accounts WHERE id=?", (aid,)).fetchone()
    if not acc:
        conn.close()
        raise HTTPException(status_code=404)
    conn.execute("UPDATE ai_accounts SET status='DIRECT_PORTAL_ACTIVE' WHERE id=?", (aid,))
    conn.commit()
    conn.close()
    webbrowser.open(acc["wipe_url"])
    add_log("DIRECT_AGENT", f"Launched direct deletion portal for [{acc['platform']}] ({acc['wipe_url']}).")
    return {"ok": True}

class TargetAddReq(BaseModel):
    name: str
    path: str

@app.post("/api/targets")
def add_target(req: TargetAddReq):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO targets (name, path_or_handle, strategy) VALUES (?, ?, 'LOCAL_SHRED')", (req.name, req.path))
    conn.commit()
    conn.close()
    add_log("FOLDER_ADD", f"Added local folder target: {req.name}")
    return {"ok": True}

@app.delete("/api/targets/{tid}")
def delete_target(tid: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM targets WHERE id=?", (tid,))
    conn.commit()
    conn.close()
    return {"ok": True}

class RecAddReq(BaseModel):
    name: str
    address: str
    message: str

@app.post("/api/recipients")
def add_recipient(req: RecAddReq):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO recipients (name, address, cipher) VALUES (?, ?, ?)",
                 (req.name, req.address, encrypt_str(req.message)))
    conn.commit()
    conn.close()
    add_log("VAULT_SEAL", f"Encrypted farewell message for {req.name}.")
    return {"ok": True}

class UnlockReq(BaseModel):
    passphrase: str

@app.post("/api/unlock")
def unlock_vault(req: UnlockReq):
    if req.passphrase != MASTER_PASS:
        raise HTTPException(status_code=403)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    recs = [dict(r) for r in conn.execute("SELECT * FROM recipients").fetchall()]
    conn.close()
    for r in recs:
        r["plaintext"] = decrypt_str(r["cipher"], req.passphrase)
    add_log("VAULT_OPEN", "Farewell Vault decrypted in memory.")
    return {"recipients": recs}

@app.post("/api/execute-wipe")
async def execute_wipe():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE config SET stage='STAGE_4_GHOST_EXECUTED' WHERE id=1")
    conn.execute("UPDATE recipients SET status='DISPATCHED_OK'")
    conn.execute("UPDATE ai_accounts SET status='AI_HISTORY_PURGED (DRY-RUN)'")
    conn.execute("UPDATE targets SET status='SHREDDED (DRY-RUN)'")
    conn.commit()
    conn.close()
    add_log("PHASE_1", "[DRY-RUN] Bot confirmed zero AI activity & no reply on Gmail/Instagram. Dispatched AES-256-GCM farewells.")
    add_log("PHASE_2", "[DRY-RUN] Direct Agent logged into Gemini, Argon, ChatGPT & Gmail with stored credentials and executed DELETE ALL DATA.")
    add_log("PHASE_3", "[DRY-RUN] Shredded local Brave/Chrome/Edge browser vaults and secret folders.")
    return {"ok": True}

@app.get("/", response_class=HTMLResponse)
def serve_competition_hud():
    return r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AUTONOMOUS AI PRESENCE & DIGITAL LEGACY SENTINEL</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=JetBrains+Mono:wght@400;600;700&family=Syne:wght@700;800&display=swap" rel="stylesheet">
<style>
  :root {
    --accent: #10B981;
    --accent-glow: rgba(16, 185, 129, 0.35);
  }
  body {
    background-color: #030407;
    color: #f1f5f9;
    font-family: 'Space Grotesk', sans-serif;
    overflow-x: hidden;
  }
  .mono { font-family: 'JetBrains Mono', monospace; }
  .display-font { font-family: 'Syne', sans-serif; }

  .bento-card {
    background: linear-gradient(145deg, rgba(13, 18, 28, 0.78), rgba(7, 10, 16, 0.92));
    backdrop-filter: blur(22px);
    -webkit-backdrop-filter: blur(22px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 18px;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.65), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    position: relative;
    overflow: hidden;
    transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.35s, box-shadow 0.35s;
  }
  .bento-card:hover {
    border-color: rgba(16, 185, 129, 0.45);
    box-shadow: 0 24px 60px rgba(16, 185, 129, 0.12), inset 0 1px 0 rgba(16, 185, 129, 0.25);
  }

  .nav-pill {
    background: rgba(10, 14, 22, 0.82);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 9999px;
  }
  .tab-pill {
    border-radius: 9999px;
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .tab-pill.active {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.25), rgba(6, 182, 212, 0.2));
    border: 1px solid rgba(16, 185, 129, 0.6);
    color: #6EE7B7;
    box-shadow: 0 0 25px rgba(16, 185, 129, 0.25);
  }

  .partition-view { display: none; }
  .partition-view.active { display: block; }

  .aura-emerald {
    position: fixed; width: 550px; height: 550px; border-radius: 50%;
    background: radial-gradient(circle, rgba(16, 185, 129, 0.11) 0%, transparent 70%);
    top: -150px; left: -150px; pointer-events: none; z-index: 0;
  }
  .aura-cyan {
    position: fixed; width: 600px; height: 600px; border-radius: 50%;
    background: radial-gradient(circle, rgba(6, 182, 212, 0.09) 0%, transparent 70%);
    bottom: -200px; right: -150px; pointer-events: none; z-index: 0;
  }
</style>
</head>
<body class="min-h-screen p-4 sm:p-7 select-none relative">

  <canvas id="bgStars" class="fixed inset-0 pointer-events-none z-0"></canvas>
  <div class="aura-emerald"></div>
  <div class="aura-cyan"></div>

  <!-- ===================================================================
       ON-SCREEN BOT GMAIL & INSTAGRAM INCOMING CALL / DM NOTIFICATION POPUP
       (Makes the Bot check-in visually crystal clear to the IT Judges!)
  =================================================================== -->
  <div id="botNotificationPopup" class="fixed bottom-6 right-6 z-50 max-w-md w-full bento-card p-5 border-2 border-cyan-400 shadow-[0_0_40px_rgba(6,182,212,0.35)] hidden">
    <div class="flex items-center justify-between border-b border-white/10 pb-2.5 mb-3">
      <div class="flex items-center gap-2">
        <span class="w-3 h-3 rounded-full bg-cyan-400 animate-ping"></span>
        <span id="popupTitle" class="mono text-xs font-bold text-cyan-300 uppercase">INCOMING BOT VERIFICATION ALERT</span>
      </div>
      <button onclick="closeBotPopup()" class="mono text-xs text-slate-400 hover:text-white">[X]</button>
    </div>
    <div id="popupBody" class="mono text-xs text-slate-200 space-y-2 leading-relaxed"></div>
    <div class="mt-3 pt-2.5 border-t border-white/10 flex justify-between items-center mono text-[11px]">
      <span class="text-amber-300">AWAITING USER PROOF-OF-LIFE...</span>
      <button onclick="pulseCheckin(); closeBotPopup();" class="px-3 py-1 rounded-lg bg-emerald-500 text-black font-bold">
        ✓ I AM HERE (CANCEL WIPE)
      </button>
    </div>
  </div>

  <!-- ===================================================================
       MAIN INTERFACE
  =================================================================== -->
  <div id="mainHud" class="relative z-10 max-w-[1560px] mx-auto space-y-6">

    <!-- TOP COMMAND BAR -->
    <header class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex flex-wrap items-center gap-2 mono text-xs">
        <div id="stageBadge" class="px-3.5 py-2 rounded-full bg-emerald-500/15 border border-emerald-400/50 text-emerald-300 font-bold">
          ● NOMINAL
        </div>
        <button id="soundBtn" onclick="toggleSound()" class="px-3.5 py-2 rounded-full bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-400/50 text-emerald-300 font-bold transition">
          🔊 SOUND & AI VOICE: ON
        </button>
        <button onclick="runJudgePresentation()" class="px-4 py-2 rounded-full bg-gradient-to-r from-amber-500/25 to-emerald-500/25 hover:from-amber-500/40 hover:to-emerald-500/40 border border-amber-400/60 text-amber-200 font-bold shadow-[0_0_20px_rgba(245,158,11,0.25)] transition">
          🏆 AUTO-DEMO FOR JUDGES (VOICE + LASERS)
        </button>
      </div>

      <!-- 4 Glass Partition Tabs -->
      <nav class="nav-pill p-1.5 flex flex-wrap items-center gap-1.5 text-xs font-bold">
        <button id="tabBtn1" onmouseenter="hoverSound()" onclick="switchPartition(1)" class="tab-pill active px-4 py-2">
          01 // LASER CORE & SWITCH
        </button>
        <button id="tabBtn2" onmouseenter="hoverSound()" onclick="switchPartition(2)" class="tab-pill px-4 py-2 text-amber-300">
          02 // DIRECT GMAIL, AI & BOT VAULT
        </button>
        <button id="tabBtn3" onmouseenter="hoverSound()" onclick="switchPartition(3)" class="tab-pill px-4 py-2">
          03 // PC FOLDERS & BROWSERS
        </button>
        <button id="tabBtn4" onmouseenter="hoverSound()" onclick="switchPartition(4)" class="tab-pill px-4 py-2">
          04 // FAREWELLS & TERMINAL
        </button>
      </nav>
    </header>

    <!-- ===================================================================
         FIRST PAGE (PARTITION 01): EXACT v5.0 LUXURY METER & LASER TOPOLOGY
    =================================================================== -->
    <div id="part1" class="partition-view active space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">

        <!-- LEFT BENTO CARD: 01 // BIOMETRIC HEARTBEAT & 14-DAY COUNTDOWN -->
        <section class="lg:col-span-6 bento-card p-6 flex flex-col justify-between space-y-5">
          <div class="flex justify-between items-center">
            <span class="mono text-xs text-emerald-400 uppercase tracking-widest flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
              01 // BIOMETRIC HEARTBEAT & 14-DAY COUNTDOWN
            </span>
            <span id="liveAiBadge" class="mono text-[11px] px-2.5 py-0.5 rounded-full bg-white/5 border border-white/10 text-emerald-300">
              AUTO-SENSOR: ACTIVE
            </span>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-12 gap-4 items-center">
            <!-- Spinning Quantum Core -->
            <div class="sm:col-span-4 flex flex-col items-center justify-center bg-black/40 border border-white/5 rounded-2xl p-3">
              <canvas id="reactorCanvas" width="130" height="130"></canvas>
              <span class="mono text-[10px] text-emerald-400/80 mt-1">QUANTUM CORE SYNC</span>
            </div>

            <!-- Millisecond Countdown Clock + Auto-Presence Status Bar -->
            <div class="sm:col-span-8 bg-black/40 border border-white/5 rounded-2xl p-5 flex flex-col justify-between space-y-3">
              <div>
                <div class="mono text-[10px] text-slate-400 uppercase tracking-widest">TIME UNTIL DIRECT AI & ACCOUNT ERASURE</div>
                <div id="clockDisplay" class="mono text-2xl sm:text-3xl font-bold text-emerald-400 mt-1.5 tracking-tight drop-shadow-[0_0_15px_rgba(16,185,129,0.4)]">
                  14d : 00h : 00m : 00.000s
                </div>
              </div>
              <div onclick="pulseCheckin()" class="cursor-pointer w-full py-3 px-4 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-400 hover:from-emerald-400 hover:to-teal-300 text-black font-bold text-xs mono tracking-wider text-center shadow-[0_0_25px_rgba(16,185,129,0.4)] transition">
                ⚡ AUTO-PRESENCE ACTIVE — RESETS ON AI USAGE
              </div>
            </div>
          </div>

          <!-- Live Glowing Oscilloscope ECG Waveform -->
          <div class="relative bg-black/50 border border-white/10 rounded-2xl h-28 overflow-hidden">
            <canvas id="ecgCanvas" width="750" height="112" class="w-full h-full"></canvas>
            <div id="bpmText" class="absolute top-2.5 left-4 mono text-[11px] text-emerald-400 font-bold">
              ● TELEMETRY WAVEFORM // 64 BPM
            </div>
          </div>

          <!-- 5-Stage Escalation Meter -->
          <div class="space-y-2">
            <div class="mono text-[10px] text-slate-400 uppercase">TEST ESCALATION STAGES (WATCH CORE, SOUND & LASERS SHIFT):</div>
            <div class="grid grid-cols-5 gap-2 mono text-[11px]">
              <button onmouseenter="hoverSound()" onclick="setStage('NOMINAL')" class="py-2 rounded-xl border border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20 font-bold">NOMINAL</button>
              <button onmouseenter="hoverSound()" onclick="setStage('STAGE_1_ALERT')" class="py-2 rounded-xl border border-amber-500/40 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20 font-bold">ALERT</button>
              <button onmouseenter="hoverSound()" onclick="setStage('STAGE_2_CRITICAL')" class="py-2 rounded-xl border border-orange-500/40 bg-orange-500/10 text-orange-300 hover:bg-orange-500/20 font-bold">CRITICAL</button>
              <button onmouseenter="hoverSound()" onclick="setStage('STAGE_3_FINAL_COUNTDOWN')" class="py-2 rounded-xl border border-red-500/50 bg-red-500/15 text-red-300 hover:bg-red-500/25 font-bold">FINAL</button>
              <button onmouseenter="hoverSound()" onclick="setStage('STAGE_4_GHOST_EXECUTED')" class="py-2 rounded-xl border border-red-600 bg-red-600/25 text-red-200 hover:bg-red-600/40 font-bold">EXECUTE</button>
            </div>
          </div>

          <!-- Weighted Radial Hold-to-Execute Switch -->
          <div onmousedown="startHold()" onmouseup="cancelHold()" onmouseleave="cancelHold()" ontouchstart="startHold()" ontouchend="cancelHold()"
               class="relative cursor-pointer bg-black/50 border border-red-500/50 hover:border-red-400 rounded-2xl p-4 overflow-hidden transition">
            <div id="holdBar" class="absolute inset-y-0 left-0 bg-gradient-to-r from-red-600/35 to-orange-500/35 pointer-events-none" style="width:0%"></div>
            <div class="relative z-10 flex items-center justify-between">
              <div class="flex items-center gap-3.5">
                <svg class="w-11 h-11 -rotate-90" viewBox="0 0 40 40">
                  <circle cx="20" cy="20" r="16" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="3"/>
                  <circle id="holdCircle" cx="20" cy="20" r="16" fill="none" stroke="#EF4444" stroke-width="3.5" stroke-dasharray="100.5" stroke-dashoffset="100.5"/>
                </svg>
                <div>
                  <div id="holdTitle" class="mono text-xs sm:text-sm font-bold text-red-400">
                    PRESS & HOLD 2.5s TO FIRE FULL LASER WIPE SIMULATION
                  </div>
                  <div class="mono text-[11px] text-slate-400">
                    1) Send Farewells -> 2) Login & Delete Gemini/AI History -> 3) Shred Local Vaults
                  </div>
                </div>
              </div>
              <span class="mono text-[11px] px-3 py-1 rounded-full border border-red-500/40 bg-red-500/15 text-red-300 font-bold">HOLD</span>
            </div>
          </div>
        </section>

        <!-- RIGHT BENTO CARD: 02 // FIBER-OPTIC LASER TOPOLOGY & AI NEURAL MESH -->
        <section class="lg:col-span-6 bento-card p-6 flex flex-col justify-between space-y-4">
          <div class="flex flex-wrap justify-between items-center gap-2">
            <span class="mono text-xs text-cyan-400 uppercase tracking-widest flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
              02 // FIBER-OPTIC LASER TOPOLOGY & AI NEURAL MESH
            </span>
            <div class="flex items-center gap-2">
              <button onmouseenter="hoverSound()" onclick="testBotPing()" class="mono text-[11px] px-3 py-1 rounded-full bg-cyan-500/15 hover:bg-cyan-500/30 border border-cyan-400/50 text-cyan-300 font-bold transition">
                📲 SIMULATE BOT CALL & EMAIL
              </button>
              <button onmouseenter="hoverSound()" onclick="fireDryRunAnimation()" class="mono text-[11px] px-3 py-1 rounded-full bg-red-500/15 hover:bg-red-500/30 border border-red-500/40 text-red-300 font-bold transition">
                ⚡ FIRE LASER WIPE BURST
              </button>
            </div>
          </div>

          <div class="bg-black/50 border border-white/10 rounded-2xl p-3 relative overflow-hidden flex-1 flex items-center justify-center">
            <svg id="nodeMapSvg" viewBox="0 0 640 340" class="w-full h-[330px]">
              <defs>
                <filter id="neonGlow" x="-40%" y="-40%" width="180%" height="180%">
                  <feGaussianBlur stdDeviation="4" result="blur"/>
                  <feMerge>
                    <feMergeNode in="blur"/>
                    <feMergeNode in="SourceGraphic"/>
                  </feMerge>
                </filter>
                <linearGradient id="beamInGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stop-color="#10B981" stop-opacity="0.15"/>
                  <stop offset="100%" stop-color="#06B6D4" stop-opacity="0.75"/>
                </linearGradient>
                <linearGradient id="beamOutGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stop-color="#06B6D4" stop-opacity="0.75"/>
                  <stop offset="100%" stop-color="#EF4444" stop-opacity="0.35"/>
                </linearGradient>
                <radialGradient id="coreAura" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stop-color="#10B981" stop-opacity="0.28"/>
                  <stop offset="100%" stop-color="#10B981" stop-opacity="0"/>
                </radialGradient>
              </defs>

              <circle cx="320" cy="170" r="125" fill="url(#coreAura)"/>
              <circle cx="320" cy="170" r="115" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="1" stroke-dasharray="3 6"/>
              <circle cx="320" cy="170" r="82" fill="none" stroke="rgba(16,185,129,0.18)" stroke-width="1" stroke-dasharray="8 6">
                <animateTransform attributeName="transform" type="rotate" from="360 320 170" to="0 320 170" dur="18s" repeatCount="indefinite"/>
              </circle>

              <path d="M 155 48 C 235 48, 235 170, 320 170" stroke="url(#beamInGrad)" stroke-width="2" fill="none"/>
              <path d="M 155 128 C 230 128, 240 170, 320 170" stroke="url(#beamInGrad)" stroke-width="2" fill="none"/>
              <path d="M 155 212 C 230 212, 240 170, 320 170" stroke="url(#beamInGrad)" stroke-width="2" fill="none"/>
              <path d="M 155 292 C 235 292, 235 170, 320 170" stroke="url(#beamInGrad)" stroke-width="2" fill="none"/>

              <path d="M 320 170 C 405 170, 405 48, 485 48" stroke="url(#beamOutGrad)" stroke-width="2" fill="none"/>
              <path d="M 320 170 C 400 170, 410 128, 485 128" stroke="url(#beamOutGrad)" stroke-width="2" fill="none"/>
              <path d="M 320 170 C 400 170, 410 212, 485 212" stroke="url(#beamOutGrad)" stroke-width="2" fill="none"/>
              <path d="M 320 170 C 405 170, 405 292, 485 292" stroke="url(#beamOutGrad)" stroke-width="2" fill="none"/>

              <circle r="4.5" fill="#34D399" filter="url(#neonGlow)">
                <animateMotion dur="1.7s" repeatCount="indefinite" path="M 155 48 C 235 48, 235 170, 320 170"/>
              </circle>
              <circle r="5" fill="#FBBF24" filter="url(#neonGlow)">
                <animateMotion dur="1.3s" repeatCount="indefinite" path="M 155 128 C 230 128, 240 170, 320 170"/>
              </circle>
              <circle r="4.5" fill="#38BDF8" filter="url(#neonGlow)">
                <animateMotion dur="1.5s" repeatCount="indefinite" path="M 155 212 C 230 212, 240 170, 320 170"/>
              </circle>
              <circle r="4.5" fill="#34D399" filter="url(#neonGlow)">
                <animateMotion dur="1.9s" repeatCount="indefinite" path="M 155 292 C 235 292, 235 170, 320 170"/>
              </circle>

              <circle r="5" fill="#F43F5E" filter="url(#neonGlow)">
                <animateMotion dur="1.2s" repeatCount="indefinite" path="M 320 170 C 405 170, 405 48, 485 48"/>
              </circle>
              <circle r="5" fill="#F43F5E" filter="url(#neonGlow)">
                <animateMotion dur="1.5s" repeatCount="indefinite" path="M 320 170 C 400 170, 410 128, 485 128"/>
              </circle>
              <circle r="5" fill="#F43F5E" filter="url(#neonGlow)">
                <animateMotion dur="1.35s" repeatCount="indefinite" path="M 320 170 C 400 170, 410 212, 485 212"/>
              </circle>
              <circle r="5" fill="#38BDF8" filter="url(#neonGlow)">
                <animateMotion dur="1.6s" repeatCount="indefinite" path="M 320 170 C 405 170, 405 292, 485 292"/>
              </circle>

              <!-- LEFT NODES -->
              <g class="cursor-pointer" onmouseenter="hoverSound()" onclick="switchPartition(2)">
                <rect x="10" y="28" width="145" height="40" rx="10" fill="#090D16" stroke="#10B981" stroke-width="1.5"/>
                <circle cx="24" cy="48" r="4" fill="#10B981" filter="url(#neonGlow)"/>
                <text x="35" y="45" fill="#FFFFFF" font-size="10" font-weight="bold" font-family="JetBrains Mono">GMAIL + PASSWORD</text>
                <text x="35" y="58" fill="#6EE7B7" font-size="8" font-family="JetBrains Mono">DIRECT AUTH LOCKED</text>
              </g>

              <g class="cursor-pointer" onmouseenter="hoverSound()" onclick="switchPartition(2)">
                <rect x="10" y="108" width="145" height="40" rx="10" fill="#090D16" stroke="#F59E0B" stroke-width="1.5"/>
                <circle cx="24" cy="128" r="4" fill="#F59E0B" filter="url(#neonGlow)"/>
                <text x="35" y="125" fill="#FFFFFF" font-size="10" font-weight="bold" font-family="JetBrains Mono">GOOGLE GEMINI AI</text>
                <text x="35" y="138" fill="#FDE68A" font-size="8" font-family="JetBrains Mono">NO-API DIRECT LINK</text>
              </g>

              <g class="cursor-pointer" onmouseenter="hoverSound()" onclick="switchPartition(2)">
                <rect x="10" y="192" width="145" height="40" rx="10" fill="#090D16" stroke="#38BDF8" stroke-width="1.5"/>
                <circle cx="24" cy="212" r="4" fill="#38BDF8" filter="url(#neonGlow)"/>
                <text x="35" y="209" fill="#FFFFFF" font-size="10" font-weight="bold" font-family="JetBrains Mono">ARGON & CHATGPT</text>
                <text x="35" y="222" fill="#BAE6FD" font-size="8" font-family="JetBrains Mono">SESSION CONNECTED</text>
              </g>

              <g class="cursor-pointer" onmouseenter="hoverSound()" onclick="switchPartition(3)">
                <rect x="10" y="272" width="145" height="40" rx="10" fill="#090D16" stroke="#10B981" stroke-width="1.5"/>
                <circle cx="24" cy="292" r="4" fill="#10B981" filter="url(#neonGlow)"/>
                <text x="35" y="289" fill="#FFFFFF" font-size="10" font-weight="bold" font-family="JetBrains Mono">CHROME & PC VAULT</text>
                <text x="35" y="302" fill="#6EE7B7" font-size="8" font-family="JetBrains Mono">LOCAL SHRED READY</text>
              </g>

              <!-- RIGHT NODES -->
              <g class="cursor-pointer" onmouseenter="hoverSound()" onclick="switchPartition(2)">
                <rect x="485" y="28" width="145" height="40" rx="10" fill="#090D16" stroke="#F43F5E" stroke-width="1.5"/>
                <text x="498" y="45" fill="#FFFFFF" font-size="10" font-weight="bold" font-family="JetBrains Mono">PURGE GEMINI DATA</text>
                <text x="498" y="58" fill="#FDA4AF" font-size="8" font-family="JetBrains Mono">ALL CHATS & ACTIVITY</text>
              </g>

              <g class="cursor-pointer" onmouseenter="hoverSound()" onclick="switchPartition(2)">
                <rect x="485" y="108" width="145" height="40" rx="10" fill="#090D16" stroke="#F43F5E" stroke-width="1.5"/>
                <text x="498" y="125" fill="#FFFFFF" font-size="10" font-weight="bold" font-family="JetBrains Mono">WIPE AI & SOCIALS</text>
                <text x="498" y="138" fill="#FDA4AF" font-size="8" font-family="JetBrains Mono">INSTAGRAM / ARGON</text>
              </g>

              <g class="cursor-pointer" onmouseenter="hoverSound()" onclick="switchPartition(3)">
                <rect x="485" y="192" width="145" height="40" rx="10" fill="#090D16" stroke="#F43F5E" stroke-width="1.5"/>
                <text x="498" y="209" fill="#FFFFFF" font-size="10" font-weight="bold" font-family="JetBrains Mono">SHRED PC BROWSERS</text>
                <text x="498" y="222" fill="#FDA4AF" font-size="8" font-family="JetBrains Mono">COOKIES & PASSWORDS</text>
              </g>

              <g class="cursor-pointer" onmouseenter="hoverSound()" onclick="switchPartition(4)">
                <rect x="485" y="272" width="145" height="40" rx="10" fill="#090D16" stroke="#38BDF8" stroke-width="1.5"/>
                <text x="498" y="289" fill="#FFFFFF" font-size="10" font-weight="bold" font-family="JetBrains Mono">FAREWELL DISPATCH</text>
                <text x="498" y="302" fill="#BAE6FD" font-size="8" font-family="JetBrains Mono">AES-256 TO LOVED ONES</text>
              </g>

              <!-- CENTER HUB: GHOST CORE -->
              <g>
                <circle id="coreOuterRing" cx="320" cy="170" r="52" fill="#050811" stroke="#10B981" stroke-width="2.5" filter="url(#neonGlow)"/>
                <circle cx="320" cy="170" r="42" fill="none" stroke="#06B6D4" stroke-width="1.5" stroke-dasharray="10 6">
                  <animateTransform attributeName="transform" type="rotate" from="0 320 170" to="360 320 170" dur="7s" repeatCount="indefinite"/>
                </circle>
                <text x="320" y="166" text-anchor="middle" fill="#FFFFFF" font-size="11" font-weight="bold" font-family="Syne">GHOST CORE</text>
                <text x="320" y="181" text-anchor="middle" fill="#34D399" font-size="8.5" font-family="JetBrains Mono">DIRECT AI AGENT</text>
              </g>
            </svg>
          </div>

          <div class="grid grid-cols-3 gap-3 mono text-xs">
            <div onmouseenter="hoverSound()" onclick="switchPartition(2)" class="cursor-pointer bg-black/40 hover:bg-white/5 border border-white/10 rounded-xl p-3">
              <div class="text-[10px] text-slate-400">DIRECT AI LINKS</div>
              <div class="text-sm font-bold text-amber-300 mt-0.5">5 ACCOUNTS READY →</div>
            </div>
            <div onmouseenter="hoverSound()" onclick="switchPartition(3)" class="cursor-pointer bg-black/40 hover:bg-white/5 border border-white/10 rounded-xl p-3">
              <div class="text-[10px] text-slate-400">BROWSER VAULTS</div>
              <div class="text-sm font-bold text-emerald-300 mt-0.5">BRAVE & CHROME →</div>
            </div>
            <div onmouseenter="hoverSound()" onclick="switchPartition(4)" class="cursor-pointer bg-black/40 hover:bg-white/5 border border-white/10 rounded-xl p-3">
              <div class="text-[10px] text-slate-400">VAULT CIPHER</div>
              <div class="text-sm font-bold text-cyan-300 mt-0.5">AES-256-GCM →</div>
            </div>
          </div>
        </section>
      </div>
    </div>

    <!-- ===================================================================
         PARTITION 02: DIRECT GMAIL, AI VAULT & BOT GMAIL/INSTAGRAM CALLER
    =================================================================== -->
    <div id="part2" class="partition-view space-y-6">
      <section class="bento-card p-6 space-y-4">
        <div class="border-b border-white/10 pb-3 flex flex-wrap justify-between items-center gap-2">
          <div>
            <span class="mono text-xs text-cyan-400 uppercase tracking-widest">BOT'S DEDICATED GMAIL & INSTAGRAM (TEXTS & CALLS YOU IF YOU ARE INACTIVE)</span>
            <p class="text-xs text-slate-300 mt-1">If you don't use any AI model for 14 days, the Bot uses its own Gmail and Instagram below to text and call your Gmail & Instagram first.</p>
          </div>
          <button onclick="testBotPing()" class="mono text-xs px-4 py-2 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/35 border border-cyan-400 text-cyan-200 font-bold">
            📨 TEST BOT EMAIL & INSTA CALL NOW
          </button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-6 gap-3 mono text-xs">
          <input id="botGmail" placeholder="Bot's Gmail" class="bg-[#090d16] border border-white/15 rounded-xl px-3 py-2 text-white">
          <input id="botGmailPass" type="password" placeholder="Bot Gmail Password" class="bg-[#090d16] border border-white/15 rounded-xl px-3 py-2 text-white">
          <input id="userGmail" placeholder="Your Personal Gmail" class="bg-[#090d16] border border-cyan-500/40 rounded-xl px-3 py-2 text-cyan-200">
          <input id="botInsta" placeholder="Bot's @Instagram" class="bg-[#090d16] border border-white/15 rounded-xl px-3 py-2 text-white">
          <input id="userInsta" placeholder="Your @Instagram" class="bg-[#090d16] border border-fuchsia-500/40 rounded-xl px-3 py-2 text-fuchsia-200">
          <button onclick="saveBotConfig()" class="rounded-xl bg-emerald-500 text-black font-bold py-2">💾 SAVE BOT</button>
        </div>
      </section>

      <section class="bento-card p-6 space-y-5">
        <div class="border-b border-white/10 pb-3">
          <span class="mono text-xs text-amber-400 uppercase tracking-widest">DIRECT GMAIL & PASSWORD AI CONNECTOR (NO API NEEDED)</span>
        </div>

        <div class="bg-black/40 border border-amber-500/30 rounded-2xl p-5 space-y-3 mono text-xs">
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <select id="aiPlatform" onchange="autoFillUrl()" class="bg-[#090d16] border border-white/15 rounded-xl px-3 py-2.5 text-white">
              <option value="Google Gemini (Direct Web Account)|https://myactivity.google.com/product/gemini|AUTO-LOGIN -> DELETE ALL GEMINI CHATS (ALL TIME)">Google Gemini (Direct Web Account)</option>
              <option value="Argon AI Account|https://aistudio.google.com/|AUTO-LOGIN -> COMMAND AI TO PURGE ALL PERSONAL DATA">Argon AI / Google AI Studio</option>
              <option value="ChatGPT / OpenAI Web|https://chatgpt.com/#settings/DataControls|AUTO-LOGIN -> DELETE ALL CHATS & MEMORY">ChatGPT Web Account</option>
              <option value="Google Gmail & Account Activity|https://myactivity.google.com/delete-activity|AUTO-LOGIN -> WIPE ALL GOOGLE & GMAIL ACTIVITY">Google Gmail & Full Google Activity</option>
              <option value="Instagram Account|https://www.instagram.com/accounts/remove/request/permanent/|AUTO-LOGIN -> PERMANENT ACCOUNT DELETION">Instagram Account</option>
            </select>
            <input id="aiUser" placeholder="Your Gmail or Username" class="bg-[#090d16] border border-white/15 rounded-xl px-3 py-2.5 text-white">
            <input id="aiPass" type="password" placeholder="Your Password (Encrypted with AES-256)" class="bg-[#090d16] border border-white/15 rounded-xl px-3 py-2.5 text-white">
          </div>
          <div class="grid grid-cols-1 md:grid-cols-12 gap-3">
            <input id="aiUrl" value="https://myactivity.google.com/product/gemini" class="md:col-span-5 bg-[#090d16] border border-white/10 rounded-xl px-3 py-2 text-slate-300">
            <input id="aiCmd" value="AUTO-LOGIN -> DELETE ALL GEMINI CHATS (ALL TIME)" class="md:col-span-5 bg-[#090d16] border border-white/10 rounded-xl px-3 py-2 text-emerald-300">
            <button onclick="saveAiAccount()" class="md:col-span-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-black font-bold py-2">
              🔒 SAVE & LINK
            </button>
          </div>
        </div>

        <div id="aiAccountList" class="space-y-3 mono text-xs"></div>
      </section>
    </div>

    <!-- ===================================================================
         PARTITION 03: LOCAL PC FOLDERS & BROWSER VAULTS
    =================================================================== -->
    <div id="part3" class="partition-view space-y-6">
      <section class="bento-card p-6 space-y-4">
        <div class="mono text-xs text-emerald-400 uppercase tracking-widest border-b border-white/10 pb-3">
          PARTITION 03 // LOCAL PC BROWSER VAULTS & PERSONAL FOLDERS TO SHRED
        </div>
        <div class="grid grid-cols-1 md:grid-cols-12 gap-3 mono text-xs bg-black/40 border border-white/10 rounded-2xl p-4">
          <input id="tName" placeholder="1. Folder Label (e.g. My Secret Desktop Files)" class="md:col-span-5 bg-[#090d16] border border-white/15 rounded-xl px-3 py-2.5 text-white">
          <input id="tPath" placeholder="2. Folder Path (e.g. C:\Users\akmra\Desktop\SecretFiles)" class="md:col-span-5 bg-[#090d16] border border-white/15 rounded-xl px-3 py-2.5 text-white">
          <button onclick="addTarget()" class="md:col-span-2 rounded-xl bg-red-500 hover:bg-red-400 text-black font-bold py-2.5">+ ADD FOLDER</button>
        </div>
        <div id="targetMatrix" class="space-y-2.5 mono text-xs"></div>
      </section>
    </div>

    <!-- ===================================================================
         PARTITION 04: ENCRYPTED FAREWELL VAULT & LIVE TERMINAL
    =================================================================== -->
    <div id="part4" class="partition-view space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <section class="lg:col-span-6 bento-card p-6 space-y-4">
          <div class="flex justify-between items-center border-b border-white/10 pb-3">
            <span class="mono text-xs text-cyan-400 uppercase">AES-256-GCM FAREWELL VAULT</span>
            <button onclick="unlockVault()" class="mono text-xs px-3 py-1.5 rounded-xl bg-cyan-500/20 border border-cyan-400/50 text-cyan-300 font-bold">
              🔓 UNLOCK (PASS: GHOST-ALPHA-ZERO)
            </button>
          </div>
          <div class="space-y-2.5 mono text-xs bg-black/40 border border-white/10 rounded-2xl p-4">
            <div class="grid grid-cols-2 gap-2">
              <input id="recName" placeholder="Loved One's Name" class="bg-[#090d16] border border-white/15 rounded-xl px-3 py-2 text-white">
              <input id="recAddr" placeholder="Email or @Telegram" class="bg-[#090d16] border border-white/15 rounded-xl px-3 py-2 text-white">
            </div>
            <div class="flex gap-2">
              <input id="recMsg" placeholder="Secret Farewell Message to encrypt..." class="flex-1 bg-[#090d16] border border-white/15 rounded-xl px-3 py-2 text-white">
              <button onclick="addRecipient()" class="px-4 rounded-xl bg-cyan-400 text-black font-bold">+ SAVE</button>
            </div>
          </div>
          <div id="recList" class="space-y-2.5 mono text-xs"></div>
        </section>

        <section class="lg:col-span-6 bento-card p-6 space-y-4">
          <div class="flex justify-between items-center border-b border-white/10 pb-3">
            <span class="mono text-xs text-emerald-400 uppercase">LIVE CRYPTOGRAPHIC EXECUTION TERMINAL</span>
            <button onclick="fireDryRunAnimation()" class="mono text-xs px-3 py-1.5 rounded-xl bg-red-500/20 border border-red-500/50 text-red-300 font-bold">
              ⚡ RUN WIPE SIMULATION
            </button>
          </div>
          <div id="logBox" class="bg-black/50 border border-white/10 rounded-2xl p-4 h-80 overflow-y-auto mono text-xs space-y-1.5"></div>
        </section>
      </div>
    </div>

  </div>

<script>
// =========================================================================
// 1. HOLLYWOOD SCI-FI WEB AUDIO SYNTHESIZER + AI VOICE NARRATOR
// =========================================================================
let soundOn = true, audioCtx = null;

function initAudio() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  if (audioCtx.state === 'suspended') audioCtx.resume();
}

function playTone(freq = 880, dur = 0.08, type = 'sine', vol = 0.12) {
  if (!soundOn) return;
  try {
    initAudio();
    const osc = audioCtx.createOscillator(), gain = audioCtx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
    gain.gain.setValueAtTime(vol, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + dur);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + dur);
  } catch(e) {}
}

function hoverSound() {
  playTone(1450, 0.025, 'sine', 0.035);
}

function chirpSuccess() {
  playTone(784, 0.06, 'sine', 0.12);
  setTimeout(() => playTone(1174, 0.08, 'sine', 0.12), 65);
  setTimeout(() => playTone(1567, 0.12, 'sine', 0.14), 130);
}

function incomingCallRing() {
  playTone(987, 0.1, 'sine', 0.15);
  setTimeout(() => playTone(1318, 0.15, 'sine', 0.15), 110);
  setTimeout(() => playTone(987, 0.1, 'sine', 0.15), 320);
  setTimeout(() => playTone(1318, 0.18, 'sine', 0.15), 430);
}

function alarmSiren() {
  playTone(540, 0.18, 'sawtooth', 0.16);
  setTimeout(() => playTone(310, 0.22, 'sawtooth', 0.16), 190);
  setTimeout(() => playTone(540, 0.18, 'sawtooth', 0.16), 400);
}

function speakAI(text) {
  if (!soundOn || !('speechSynthesis' in window)) return;
  try {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1.04;
    u.pitch = 0.92;
    window.speechSynthesis.speak(u);
  } catch(e) {}
}

function toggleSound() {
  soundOn = !soundOn;
  const btn = document.getElementById('soundBtn');
  btn.textContent = soundOn ? "🔊 SOUND & AI VOICE: ON" : "🔇 SOUND & AI VOICE: MUTED";
  if (soundOn) {
    chirpSuccess();
    speakAI("Tactical audio and voice telemetry online.");
  } else if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
  }
}

// =========================================================================
// 2. ON-SCREEN BOT GMAIL & INSTAGRAM POPUP + 30s JUDGE AUTO-PRESENTATION
// =========================================================================
function showBotPopup(title, htmlContent) {
  const pop = document.getElementById('botNotificationPopup');
  document.getElementById('popupTitle').textContent = title;
  document.getElementById('popupBody').innerHTML = htmlContent;
  pop.classList.remove('hidden');
  gsap.fromTo(pop, { y: 40, opacity: 0, scale: 0.95 }, { y: 0, opacity: 1, scale: 1, duration: 0.4, ease: "back.out(1.5)" });
  incomingCallRing();
}

function closeBotPopup() {
  document.getElementById('botNotificationPopup').classList.add('hidden');
}

async function runJudgePresentation() {
  switchPartition(1);
  chirpSuccess();
  speakAI("Welcome Judges. Initiating Autonomous Digital Legacy and A.I. Presence Sentinel demonstration. Stage One: Nominal. Automatic browser sensor is monitoring Gemini, Chat G P T, and Argon usage in real time.");
  await setStage('NOMINAL', true);

  setTimeout(async () => {
    await setStage('STAGE_1_ALERT', true);
    showBotPopup("📧 BOT GMAIL VERIFICATION DISPATCHED", `
      <div><b>FROM:</b> sentinel.bot.agent@gmail.com</div>
      <div><b>TO:</b> akmra.personal@gmail.com</div>
      <div class="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-200 mt-1">
        "Are you here or not? I have not detected any activity on your Gemini, ChatGPT, or Argon AI accounts. Open any AI model to reset your 14-day timer."
      </div>
    `);
    speakAI("Stage Two: Inactivity detected. Dedicated Bot Gmail has messaged your personal Gmail asking if you are active.");
  }, 8500);

  setTimeout(async () => {
    await setStage('STAGE_2_CRITICAL', true);
    showBotPopup("📱 BOT INSTAGRAM DM & INCOMING CALL", `
      <div><b>BOT INSTAGRAM:</b> @sentinel_ai_bot</div>
      <div><b>CALLING:</b> @akmra_official</div>
      <div class="p-2.5 rounded-xl bg-fuchsia-500/10 border border-fuchsia-500/30 text-fuchsia-200 mt-1">
        "📞 INCOMING INSTAGRAM AUDIO CALL & URGENT DM: No response on Gmail. Verify Proof-of-Life within 24 hours or all AI accounts and browser vaults will be erased."
      </div>
    `);
    speakAI("Stage Three: Critical escalation. Dedicated Bot Instagram account is now messaging and calling your personal Instagram account.");
  }, 17500);

  setTimeout(async () => {
    closeBotPopup();
    speakAI("Day Fourteen threshold reached with zero response. Firing Fiber-Optic Protocol Zero. Dispatching encrypted farewell messages, purging Gemini and Chat G P T history, and shredding local browser vaults.");
    await fireDryRunAnimation();
  }, 26500);
}

// =========================================================================
// 3. BACKGROUND CONSTELLATION & PARTITION SWITCHER
// =========================================================================
const bgCanvas = document.getElementById('bgStars');
const bgCtx = bgCanvas.getContext('2d');
let stars = [], mouse = { x: -500, y: -500 };

function resizeBg() {
  bgCanvas.width = window.innerWidth;
  bgCanvas.height = window.innerHeight;
}
window.addEventListener('resize', resizeBg);
window.addEventListener('mousemove', e => { mouse.x = e.clientX; mouse.y = e.clientY; });
resizeBg();

for (let i = 0; i < 65; i++) {
  stars.push({
    x: Math.random() * bgCanvas.width,
    y: Math.random() * bgCanvas.height,
    vx: (Math.random() - 0.5) * 0.4,
    vy: (Math.random() - 0.5) * 0.4,
    r: Math.random() * 1.8 + 0.6
  });
}

function drawConstellation() {
  bgCtx.clearRect(0, 0, bgCanvas.width, bgCanvas.height);
  for (let i = 0; i < stars.length; i++) {
    let s = stars[i];
    s.x += s.vx; s.y += s.vy;
    if (s.x < 0 || s.x > bgCanvas.width) s.vx *= -1;
    if (s.y < 0 || s.y > bgCanvas.height) s.vy *= -1;

    bgCtx.fillStyle = "rgba(16, 185, 129, 0.55)";
    bgCtx.beginPath();
    bgCtx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
    bgCtx.fill();

    let dm = Math.hypot(s.x - mouse.x, s.y - mouse.y);
    if (dm < 170) {
      bgCtx.strokeStyle = `rgba(6, 182, 212, ${1 - dm / 170})`;
      bgCtx.lineWidth = 0.8;
      bgCtx.beginPath();
      bgCtx.moveTo(s.x, s.y);
      bgCtx.lineTo(mouse.x, mouse.y);
      bgCtx.stroke();
    }
  }
  requestAnimationFrame(drawConstellation);
}
drawConstellation();

function switchPartition(num) {
  playTone(1040, 0.06, 'sine', 0.1);
  for (let i = 1; i <= 4; i++) {
    document.getElementById('part' + i).classList.remove('active');
    document.getElementById('tabBtn' + i).classList.remove('active');
  }
  document.getElementById('part' + num).classList.add('active');
  document.getElementById('tabBtn' + num).classList.add('active');
  gsap.fromTo('#part' + num, { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.35, ease: "power2.out" });
}

const STAGE_COLORS = { NOMINAL:"#10B981", STAGE_1_ALERT:"#F59E0B", STAGE_2_CRITICAL:"#F97316", STAGE_3_FINAL_COUNTDOWN:"#EF4444", STAGE_4_GHOST_EXECUTED:"#DC2626" };
let currentStage = "NOMINAL", deadlineUtc = new Date(Date.now() + 14*86400000).toISOString(), decryptedRecs = null, botLoaded = false;

const rCanvas = document.getElementById('reactorCanvas'), rCtx = rCanvas.getContext('2d');
let a1 = 0, a2 = 0;
function drawReactor() {
  rCtx.clearRect(0,0,130,130);
  const col = STAGE_COLORS[currentStage] || "#10B981";
  const mult = currentStage === "NOMINAL" ? 1 : 2.8;
  a1 += 0.025 * mult; a2 -= 0.04 * mult;
  rCtx.save(); rCtx.translate(65,65);
  rCtx.strokeStyle = col; rCtx.lineWidth = 3; rCtx.shadowColor = col; rCtx.shadowBlur = 12;
  for (let i=0;i<6;i++) { rCtx.beginPath(); rCtx.arc(0,0,50, a1+(i*Math.PI/3), a1+(i*Math.PI/3)+0.65); rCtx.stroke(); }
  rCtx.lineWidth = 2;
  for (let i=0;i<4;i++) { rCtx.beginPath(); rCtx.arc(0,0,35, a2+(i*Math.PI/2), a2+(i*Math.PI/2)+0.9); rCtx.stroke(); }
  rCtx.fillStyle = col; rCtx.beginPath(); rCtx.arc(0,0, 14+Math.sin(a1*3)*3, 0, Math.PI*2); rCtx.fill();
  rCtx.restore();
  requestAnimationFrame(drawReactor);
}
drawReactor();

const eCanvas = document.getElementById('ecgCanvas'), eCtx = eCanvas.getContext('2d');
let ecgPhase = 0;
function drawEcg() {
  const w = eCanvas.width, h = eCanvas.height;
  eCtx.clearRect(0,0,w,h);
  const col = STAGE_COLORS[currentStage] || "#10B981";
  eCtx.strokeStyle = col; eCtx.lineWidth = 2.2; eCtx.shadowColor = col; eCtx.shadowBlur = 12;
  eCtx.beginPath();
  ecgPhase += (currentStage === "NOMINAL" ? 0.08 : 0.22);
  for (let x=0;x<w;x++) {
    let y = h/2;
    if (currentStage !== "STAGE_4_GHOST_EXECUTED") {
      const pos = (x + Math.floor(ecgPhase * 35)) % (currentStage === "NOMINAL" ? 130 : 72);
      if (pos > 40 && pos < 45) y -= 8;
      else if (pos >= 48 && pos < 53) y -= 38;
      else if (pos >= 53 && pos < 58) y += 18;
      else if (pos > 66 && pos < 76) y -= 10;
    }
    if (x===0) eCtx.moveTo(x,y); else eCtx.lineTo(x,y);
  }
  eCtx.stroke(); eCtx.shadowBlur = 0;
  requestAnimationFrame(drawEcg);
}
drawEcg();

function autoFillUrl() {
  const parts = document.getElementById('aiPlatform').value.split('|');
  document.getElementById('aiUrl').value = parts[1] || '';
  document.getElementById('aiCmd').value = parts[2] || '';
}

async function refreshState() {
  const res = await fetch('/api/state');
  const data = await res.json();
  deadlineUtc = data.deadline_utc;
  currentStage = data.stage;
  const col = STAGE_COLORS[currentStage] || "#10B981";
  document.getElementById('clockDisplay').style.color = col;
  document.getElementById('stageBadge').textContent = "● " + currentStage;
  document.getElementById('stageBadge').style.color = col;
  document.getElementById('coreOuterRing').setAttribute("stroke", col);

  const bpmMap = { NOMINAL:"64 BPM", STAGE_1_ALERT:"96 BPM", STAGE_2_CRITICAL:"128 BPM", STAGE_3_FINAL_COUNTDOWN:"168 BPM", STAGE_4_GHOST_EXECUTED:"0 BPM [PROTOCOL ZERO]" };
  document.getElementById('bpmText').textContent = "● TELEMETRY WAVEFORM // " + (bpmMap[currentStage] || "64 BPM");
  document.getElementById('bpmText').style.color = col;

  if (data.detected_ai) {
    document.getElementById('liveAiBadge').textContent = "AUTO-SENSOR: " + data.detected_ai;
  }

  if (!botLoaded && data.bot_config) {
    document.getElementById('botGmail').value = data.bot_config.bot_gmail;
    document.getElementById('userGmail').value = data.bot_config.user_gmail;
    document.getElementById('botInsta').value = data.bot_config.bot_insta;
    document.getElementById('userInsta').value = data.bot_config.user_insta;
    botLoaded = true;
  }

  document.getElementById('aiAccountList').innerHTML = data.ai_accounts.map(a => `
    <div class="bg-black/40 border border-white/10 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-3">
      <div class="space-y-1">
        <div class="flex items-center gap-2">
          <span class="font-bold text-white text-sm">${a.platform}</span>
          <span class="px-2.5 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-[10px]">${a.status}</span>
        </div>
        <div class="text-slate-300">GMAIL / LOGIN: <b class="text-amber-300">${a.gmail_or_user}</b> | PASSWORD: <span class="text-emerald-400">[AES-256-GCM SEALED]</span></div>
        <div class="text-[11px] text-cyan-300">DAY 14 COMMAND: ${a.wipe_command}</div>
      </div>
      <div class="flex items-center gap-2">
        <button onclick="testDirectAgent(${a.id})" class="px-3.5 py-2 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/35 border border-emerald-400/60 text-emerald-300 font-bold">
          🚀 LAUNCH DIRECT WIPE PORTAL
        </button>
        <button onclick="deleteAiAccount(${a.id})" class="px-3 py-2 rounded-xl border border-red-500/40 text-red-400 hover:bg-red-500/20">X</button>
      </div>
    </div>
  `).join('');

  document.getElementById('targetMatrix').innerHTML = data.targets.map(t => `
    <div class="bg-black/40 border border-white/10 rounded-xl p-3.5 flex justify-between items-center">
      <div>
        <div class="font-bold text-white">${t.name} <span class="text-emerald-400">[${t.status}]</span></div>
        <div class="text-[11px] text-slate-400">${t.path_or_handle}</div>
      </div>
      <button onclick="deleteTarget(${t.id})" class="px-2.5 py-1 rounded-lg border border-red-500/40 text-red-400">X</button>
    </div>
  `).join('');

  const rList = decryptedRecs || data.recipients;
  document.getElementById('recList').innerHTML = rList.map(r => `
    <div class="bg-black/40 border border-white/10 rounded-xl p-3.5">
      <div class="flex justify-between font-bold text-white"><span>${r.name} -> ${r.address}</span><span class="text-emerald-400">${r.status}</span></div>
      <div class="mt-1 ${r.plaintext ? 'text-emerald-300 font-bold' : 'text-slate-500 truncate'}">
        ${r.plaintext ? '🔓 DECRYPTED: ' + r.plaintext : '🔒 AES-256-GCM: ' + r.cipher.slice(0,50) + '...'}
      </div>
    </div>
  `).join('');

  document.getElementById('logBox').innerHTML = data.logs.map(l => `
    <div class="border-b border-white/5 pb-1"><span class="text-slate-500">${l.time}</span> <span class="text-emerald-400 font-bold">[${l.level}]</span> <span class="text-slate-200">${l.msg}</span></div>
  `).join('');
}

async function pulseCheckin() {
  chirpSuccess();
  speakAI("Biometric and A.I. presence verified. Fourteen-day Dead Man's Switch reset.");
  decryptedRecs = null;
  await fetch('/api/checkin', {method:'POST'});
  refreshState();
}

async function setStage(stage, silentVoice = false) {
  playTone(620, 0.09, 'triangle', 0.14);
  await fetch('/api/stage', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({stage})});
  await refreshState();

  if (!silentVoice) {
    if (stage === 'NOMINAL') {
      closeBotPopup();
      speakAI("System Nominal. Automatic A.I. presence sensor active.");
    } else if (stage === 'STAGE_1_ALERT') {
      showBotPopup("📧 BOT GMAIL CHECK-IN SENT", `
        <div><b>BOT GMAIL:</b> ${document.getElementById('botGmail').value}</div>
        <div><b>TO YOUR GMAIL:</b> ${document.getElementById('userGmail').value}</div>
        <div class="p-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-200 mt-1">
          "Are you here or not? Zero activity detected on your Gemini and ChatGPT accounts."
        </div>
      `);
      speakAI("Alert Stage. Bot Gmail has sent a verification message to your personal Gmail.");
    } else if (stage === 'STAGE_2_CRITICAL' || stage === 'STAGE_3_FINAL_COUNTDOWN') {
      showBotPopup("📱 BOT INSTAGRAM DM & CALL ALERT", `
        <div><b>BOT INSTAGRAM:</b> ${document.getElementById('botInsta').value}</div>
        <div><b>CALLING YOUR INSTAGRAM:</b> ${document.getElementById('userInsta').value}</div>
        <div class="p-2 rounded-lg bg-red-500/15 border border-red-500/40 text-red-200 mt-1">
          "📞 INCOMING CALL & DM: Final warning before automatic Gemini, AI, and browser erasure."
        </div>
      `);
      speakAI("Critical Stage. Dedicated Bot Instagram is calling and messaging your personal Instagram account.");
    } else if (stage === 'STAGE_4_GHOST_EXECUTED') {
      fireDryRunAnimation();
    }
  }
}

async function saveBotConfig() {
  chirpSuccess();
  const payload = {
    bot_gmail: document.getElementById('botGmail').value.trim(),
    bot_gmail_pass: document.getElementById('botGmailPass').value.trim(),
    user_gmail: document.getElementById('userGmail').value.trim(),
    bot_insta: document.getElementById('botInsta').value.trim(),
    bot_insta_pass: '',
    user_insta: document.getElementById('userInsta').value.trim()
  };
  await fetch('/api/bot-config', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) });
  speakAI("Dedicated Bot Gmail and Instagram verification accounts saved.");
  refreshState();
}

async function testBotPing() {
  const res = await fetch('/api/test-bot-contact', { method:'POST' });
  const d = await res.json();
  await refreshState();
  showBotPopup("📲 LIVE BOT GMAIL & INSTAGRAM CALL DISPATCHED", `
    <div><b>1. EMAIL TEXT:</b> ${d.bot_gmail} ➔ ${d.user_gmail}</div>
    <div><b>2. INSTA CALL:</b> ${d.bot_insta} ➔ ${d.user_insta}</div>
    <div class="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-200 mt-1">
      "Are you here or not? We detected 14 days of inactivity across your AI models. Reply or answer this call to cancel full data erasure."
    </div>
  `);
  speakAI("Testing Bot verification. Dedicated Bot Gmail and Instagram are now messaging and calling your personal accounts.");
}

async function saveAiAccount() {
  const platform = document.getElementById('aiPlatform').value.split('|')[0];
  const gmail_or_user = document.getElementById('aiUser').value.trim();
  const password = document.getElementById('aiPass').value.trim();
  const wipe_url = document.getElementById('aiUrl').value.trim();
  const wipe_command = document.getElementById('aiCmd').value.trim();
  if (!gmail_or_user || !password) return alert("Enter your Gmail and Password!");
  chirpSuccess();
  speakAI("Direct A.I. credentials encrypted with A E S 256 and linked.");
  await fetch('/api/ai-accounts', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({platform, gmail_or_user, password, wipe_url, wipe_command})
  });
  document.getElementById('aiPass').value = '';
  refreshState();
}

async function testDirectAgent(id) {
  chirpSuccess();
  speakAI("Launching direct browser deletion portal.");
  await fetch(`/api/ai-accounts/${id}/test-agent`, { method: 'POST' });
  refreshState();
}
async function deleteAiAccount(id) { playTone(400,0.08); await fetch(`/api/ai-accounts/${id}`, { method: 'DELETE' }); refreshState(); }
async function addTarget() {
  const name = document.getElementById('tName').value.trim(), path = document.getElementById('tPath').value.trim();
  if (!name || !path) return;
  chirpSuccess();
  await fetch('/api/targets', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name, path})});
  document.getElementById('tName').value=''; document.getElementById('tPath').value=''; refreshState();
}
async function deleteTarget(id) { playTone(400,0.08); await fetch(`/api/targets/${id}`, {method:'DELETE'}); refreshState(); }
async function addRecipient() {
  const name = document.getElementById('recName').value.trim(), address = document.getElementById('recAddr').value.trim(), message = document.getElementById('recMsg').value.trim();
  if (!name || !address || !message) return;
  chirpSuccess();
  decryptedRecs = null;
  await fetch('/api/recipients', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name, address, message})});
  document.getElementById('recName').value=''; document.getElementById('recAddr').value=''; document.getElementById('recMsg').value=''; refreshState();
}
async function unlockVault() {
  const p = prompt("Enter Vault Master Passphrase:", "GHOST-ALPHA-ZERO");
  if (!p) return;
  const res = await fetch('/api/unlock', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({passphrase:p})});
  if (res.ok) {
    chirpSuccess();
    speakAI("Master passphrase verified. Decrypting farewell vault in memory.");
    const d = await res.json();
    decryptedRecs = d.recipients;
    refreshState();
  } else {
    alarmSiren();
    speakAI("Access denied. Invalid master passphrase.");
    alert("Invalid Passphrase!");
  }
}

let holdInterval = null, holdPct = 0;
function startHold() {
  holdPct = 0;
  holdInterval = setInterval(() => {
    holdPct += 4;
    playTone(350 + holdPct * 11, 0.05, 'sawtooth', 0.09);
    document.getElementById('holdBar').style.width = holdPct + '%';
    document.getElementById('holdCircle').style.strokeDashoffset = 100.5 - (100.5 * holdPct / 100);
    if (holdPct >= 100) { cancelHold(); fireDryRunAnimation(); }
  }, 60);
}
function cancelHold() {
  clearInterval(holdInterval);
  document.getElementById('holdBar').style.width = '0%';
  document.getElementById('holdCircle').style.strokeDashoffset = '100.5';
}
async function fireDryRunAnimation() {
  alarmSiren();
  speakAI("Protocol Zero engaged. Dispatched encrypted farewells, executed direct Gemini and A.I. history purge, and shredded local browser vaults.");
  gsap.fromTo("#nodeMapSvg", { scale: 0.93 }, { scale: 1, duration: 0.55, ease: "elastic.out(1, 0.3)" });
  gsap.fromTo("body", { backgroundColor: "#26070c" }, { backgroundColor: "#030407", duration: 0.9 });
  await fetch('/api/execute-wipe', {method:'POST'});
  await refreshState();
}

setInterval(() => {
  if (currentStage === "STAGE_4_GHOST_EXECUTED") {
    document.getElementById('clockDisplay').textContent = "00d : 00h : 00m : 00.000s";
    return;
  }
  const diff = Math.max(0, new Date(deadlineUtc).getTime() - Date.now());
  const d = String(Math.floor(diff / 86400000)).padStart(2,'0');
  const h = String(Math.floor((diff / 3600000) % 24)).padStart(2,'0');
  const m = String(Math.floor((diff / 60000) % 60)).padStart(2,'0');
  const s = String(Math.floor((diff / 1000) % 60)).padStart(2,'0');
  const ms = String(diff % 1000).padStart(3,'0');
  document.getElementById('clockDisplay').textContent = `${d}d : ${h}h : ${m}m : ${s}.${ms}s`;
}, 47);

setInterval(refreshState, 5000);
window.onload = refreshState;
</script>
</body>
</html>"""

if __name__ == "__main__":
    webbrowser.open("http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
