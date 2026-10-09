#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS NUVEM — conversa no Telegram SEM o notebook.
Roda num host gratis (Render/Railway/Fly) e responde via bot.
Env vars obrigatorias: TELEGRAM_TOKEN, DONO
Env vars do cerebro (uma basta): ZEN_KEY (+ ZEN_MODEL, ZEN_BASE) ou GROQ_KEY ou GEMINI_KEY
"""
import os
import time
import threading
import logging
import requests

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
DONO = os.environ.get("DONO", "chefe")
ZEN_KEY = os.environ.get("ZEN_KEY", "")
ZEN_MODEL = os.environ.get("ZEN_MODEL", "mimo-v2.6-flash-free")
ZEN_BASE = os.environ.get("ZEN_BASE_URL", "https://opencode.ai/zen/v1/chat/completions")
GROQ_KEY = os.environ.get("GROQ_KEY", "")
GROQ_MODELS = [m.strip() for m in os.environ.get(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile,openai/gpt-oss-20b,qwen/qwen3-32b,moonshotai/kimi-k2-instruct-0905").split(",") if m.strip()]
_GROQ_OK = ""
GEMINI_KEY = os.environ.get("GEMINI_KEY", "")
CB_PHONE = os.environ.get("CALLMEBOT_PHONE", "")
CB_KEY = os.environ.get("CALLMEBOT_APIKEY", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("jarvis-nuvem")
API = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else ""

SYSTEM = (f"Voce e JARVIS, assistente pessoal de {DONO}. Fale portugues Brasil, "
          "curto e direto, maximo 3 frases. Nunca diga que e outro modelo. Voce e JARVIS.")

_hist: dict = {}

def cerebro(chat_id: int, texto: str) -> str:
    hist = _hist.setdefault(chat_id, [])[-8:]
    msgs = [{"role": "system", "content": SYSTEM}] + hist + [{"role": "user", "content": texto}]
    # 1. Zen (OpenCode)
    if ZEN_KEY:
        try:
            r = requests.post(ZEN_BASE, headers={"Authorization": f"Bearer {ZEN_KEY}",
                              "Content-Type": "application/json"},
                              json={"model": ZEN_MODEL, "messages": msgs,
                                    "max_tokens": 400, "temperature": 0.7}, timeout=60)
            if r.ok:
                resp = r.json()["choices"][0]["message"]["content"].strip()
                _hist[chat_id] = (hist + [{"role": "user", "content": texto},
                                         {"role": "assistant", "content": resp}])[-8:]
                return resp
            log.warning(f"zen {r.status_code}: {r.text[:150]}")
        except Exception as e:
            log.warning(f"zen falhou: {e}")
    # 2. Groq (gratis) — testa modelos em ordem, usa o primeiro que responder
    if GROQ_KEY:
        modelos = ([_GROQ_OK] if _GROQ_OK else []) + [m for m in GROQ_MODELS if m != _GROQ_OK]
        for _mod in modelos:
            try:
                r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                                  headers={"Authorization": f"Bearer {GROQ_KEY}",
                                           "Content-Type": "application/json"},
                                  json={"model": _mod, "messages": msgs,
                                        "max_tokens": 400, "temperature": 0.7}, timeout=60)
                if r.ok:
                    globals()["_GROQ_OK"] = _mod
                    resp = r.json()["choices"][0]["message"]["content"].strip()
                    _hist[chat_id] = (hist + [{"role": "user", "content": texto},
                                             {"role": "assistant", "content": resp}])[-8:]
                    return resp
                log.warning(f"groq {_mod} {r.status_code}: {r.text[:120]}")
            except Exception as e:
                log.warning(f"groq {_mod} falhou: {e}")
    # 3. Gemini (gratis)
    if GEMINI_KEY:
        try:
            corpo = {"system_instruction": {"parts": [{"text": SYSTEM}]},
                     "contents": [{"parts": [{"text": (m['content'] if m['role'] != 'system' else '')}]}
                                  for m in hist + [{"role": "user", "content": texto}]]}
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}",
                              json=corpo, timeout=60)
            if r.ok:
                resp = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                _hist[chat_id] = (hist + [{"role": "user", "content": texto},
                                         {"role": "assistant", "content": resp}])[-8:]
                return resp
            log.warning(f"gemini {r.status_code}: {r.text[:150]}")
        except Exception as e:
            log.warning(f"gemini falhou: {e}")
    return ("Estou sem cérebro agora (sem key válida). Configura ZEN_KEY, GROQ_KEY ou GEMINI_KEY no painel do host.")

def tg(metodo: str, **kw):
    try:
        return requests.post(f"{API}/{metodo}", json=kw, timeout=20).json()
    except Exception as e:
        log.warning(f"tg {metodo}: {e}")
        return {}

def _agora_sp():
    try:
        from zoneinfo import ZoneInfo
        import datetime as _dt
        return _dt.datetime.now(ZoneInfo("America/Sao_Paulo"))
    except Exception:
        import datetime as _dt
        return _dt.datetime.utcnow() - _dt.timedelta(hours=3)

PIADAS = [
    "Por que o computador foi ao medico? Porque estava com virus!",
    "O que o zero disse pro oito? Que cinto maneiro!",
    "Eu ia contar uma piada sobre UDP, mas voce pode nao receber.",
]

AJUDA_NUVEM = (
    "Sou o JARVIS da nuvem. Falo igual ao do PC, mas sem tela, camera e programas.\n"
    "ajuda — esta lista | hora | data | piada\n"
    "manda mensagem + texto — WhatsApp nuvem pro seu numero\n"
    "manda audio + texto — mando áudio com minha voz\n"
    "me liga + texto — te ligo e falo (gasta 1 chamada grátis)\n"
    "Resto eu converso normal."
)

def _norm(t: str) -> str:
    import unicodedata as _u
    t = t.lower().strip()
    return "".join(c for c in _u.normalize("NFD", t) if _u.category(c) != "Mn")

def _tira(texto: str, prefs: list) -> str:
    n = _norm(texto)
    for p in prefs:
        if n.startswith(_norm(p)):
            return texto[len(p):].strip()
    return texto

def comandos(chat: int, texto: str) -> bool:
    """Comandos estilo PC. Retorna True se resolveu."""
    import random as _r
    n = _norm(texto)
    if n in ("ajuda", "/help", "help", "o que voce faz", "comandos"):
        tg("sendMessage", chat_id=chat, text=AJUDA_NUVEM)
        return True
    if n in ("hora", "que horas sao", "horas"):
        tg("sendMessage", chat_id=chat,
           text=f"São {_agora_sp().strftime('%H:%M')} em São Paulo.")
        return True
    if n.startswith("data") or "que dia" in n or "dia de hoje" in n:
        dias = ["segunda-feira", "terca-feira", "quarta-feira", "quinta-feira",
                "sexta-feira", "sabado", "domingo"]
        meses = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho",
                 "agosto", "setembro", "outubro", "novembro", "dezembro"]
        a = _agora_sp()
        tg("sendMessage", chat_id=chat,
           text=f"Hoje e {dias[a.weekday()]}, {a.day} de {meses[a.month-1]} de {a.year}.")
        return True
    if "piada" in n:
        tg("sendMessage", chat_id=chat, text=_r.choice(PIADAS))
        return True
    if n.startswith(("manda mensagem", "manda nuvem", "mandar mensagem", "mandar nuvem")):
        msg = _tira(texto, ["manda mensagem ", "manda nuvem ", "mandar mensagem ",
                            "mandar nuvem ", "manda mensagem", "manda nuvem"])
        if not msg:
            tg("sendMessage", chat_id=chat, text="Que mensagem mando na nuvem?")
            return True
        if not (CB_PHONE and CB_KEY):
            tg("sendMessage", chat_id=chat, text="Nuvem sem apikey no host.")
            return True
        try:
            import urllib.parse as _up
            r = requests.get(f"https://api.callmebot.com/whatsapp.php?phone={CB_PHONE}"
                             f"&text={_up.quote(msg)}&apikey={CB_KEY}", timeout=25)
            tg("sendMessage", chat_id=chat, text="Mensagem nuvem enviada." if r.ok
               else f"Nuvem falhou: {r.text[:150]}")
        except Exception as e:
            tg("sendMessage", chat_id=chat, text=f"Nuvem falhou: {e}")
        return True
    if n.startswith(("manda audio", "manda voz", "mandar audio")):
        msg = _tira(texto, ["manda audio ", "manda voz ", "mandar audio "])
        if not msg:
            tg("sendMessage", chat_id=chat, text="Que áudio eu mando?")
            return True
        tg("sendMessage", chat_id=chat, text="Gerando o áudio...")
        ok, resp = _audio(chat, msg)
        tg("sendMessage", chat_id=chat, text="Áudio enviado." if ok else f"Áudio falhou: {resp}")
        return True
    if n.startswith(("me liga", "liga pra mim", "liga para mim", "me telefona")):
        msg = _tira(texto, ["me liga ", "liga pra mim ", "liga para mim ", "me telefona ", "me liga"])
        if not msg:
            tg("sendMessage", chat_id=chat, text="O que eu falo quando ligar?")
            return True
        if not (CB_PHONE and CB_KEY):
            tg("sendMessage", chat_id=chat, text="Ligação sem apikey no host.")
            return True
        try:
            import urllib.parse as _up
            r = requests.get(f"https://api.callmebot.com/call.php?phone={CB_PHONE}"
                             f"&text={_up.quote(msg)}&apikey={CB_KEY}&lang=pt-BR", timeout=30)
            tg("sendMessage", chat_id=chat, text="Ligando. Atende que eu falo e desligo." if r.ok
               else f"Ligação falhou: {r.text[:150]}")
        except Exception as e:
            tg("sendMessage", chat_id=chat, text=f"Ligação falhou: {e}")
        return True
    return False

def _audio(chat: int, texto: str) -> tuple:
    """TTS Antonio + sendAudio. Retorna (ok, resp)."""
    import subprocess as _sp
    import tempfile as _tf
    try:
        with _tf.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
            f.write(texto[:500])
            txtf = f.name
        tmp = txtf + ".mp3"
        r = _sp.run(["python", "-m", "edge_tts", "--voice", "pt-BR-AntonioNeural",
                     "--rate=-10%", "--pitch=-5Hz", "--file", txtf, "--write-media", tmp],
                    capture_output=True, timeout=45)
        try:
            os.unlink(txtf)
        except Exception:
            pass
        if r.returncode != 0 or not (os.path.exists(tmp) and os.path.getsize(tmp) > 1000):
            return False, "tts falhou"
        with open(tmp, "rb") as af:
            rr = requests.post(f"{API}/sendAudio", data={"chat_id": chat},
                               files={"audio": ("jarvis.mp3", af, "audio/mpeg")}, timeout=60)
        return (True, "") if rr.ok else (False, rr.text[:150])
    except Exception as e:
        return False, str(e)
    finally:
        try:
            if "tmp" in dir() and tmp and os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass


def _http_keepalive():
    """Servidor HTTP minimo pro plano FREE (Web Service exige porta aberta)."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Ok(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"JARVIS OK")
        def do_HEAD(self):
            self.send_response(200)
            self.end_headers()
        def log_message(self, *a):
            pass

    port = int(os.environ.get("PORT", "10000"))
    try:
        HTTPServer(("0.0.0.0", port), Ok).serve_forever()
    except Exception as e:
        log.warning(f"http keepalive: {e}")

def main():
    if not TOKEN:
        raise SystemExit("Falta TELEGRAM_TOKEN nas env vars.")
    threading.Thread(target=_http_keepalive, daemon=True).start()
    log.info("JARVIS nuvem online.")
    offset = 0
    while True:
        try:
            d = tg("getUpdates", offset=offset, timeout=50)
            for u in d.get("result", []):
                offset = max(offset, u["update_id"] + 1)
                m = u.get("message") or {}
                chat = m.get("chat", {}).get("id")
                texto = (m.get("text") or "").strip()
                if not chat or not texto:
                    continue
                if texto == "/start":
                    tg("sendMessage", chat_id=chat,
                       text="Olá, tudo bem? Eu sou o JARVIS e fui criado do zero pelo Noelzin.")
                    continue
                if comandos(chat, texto):
                    continue
                tg("sendChatAction", chat_id=chat, action="typing")
                tg("sendMessage", chat_id=chat, text=cerebro(chat, texto)[:4000])
        except Exception as e:
            log.warning(f"loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
