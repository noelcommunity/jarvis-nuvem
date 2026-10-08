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
import logging
import requests

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
DONO = os.environ.get("DONO", "chefe")
ZEN_KEY = os.environ.get("ZEN_KEY", "")
ZEN_MODEL = os.environ.get("ZEN_MODEL", "mimo-v2.6-flash-free")
ZEN_BASE = os.environ.get("ZEN_BASE_URL", "https://opencode.ai/zen/v1/chat/completions")
GROQ_KEY = os.environ.get("GROQ_KEY", "")
GEMINI_KEY = os.environ.get("GEMINI_KEY", "")

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
    # 2. Groq (gratis)
    if GROQ_KEY:
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                              headers={"Authorization": f"Bearer {GROQ_KEY}",
                                       "Content-Type": "application/json"},
                              json={"model": "llama-3.1-8b-instant", "messages": msgs,
                                    "max_tokens": 400, "temperature": 0.7}, timeout=60)
            if r.ok:
                resp = r.json()["choices"][0]["message"]["content"].strip()
                _hist[chat_id] = (hist + [{"role": "user", "content": texto},
                                         {"role": "assistant", "content": resp}])[-8:]
                return resp
            log.warning(f"groq {r.status_code}: {r.text[:150]}")
        except Exception as e:
            log.warning(f"groq falhou: {e}")
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

def main():
    if not TOKEN:
        raise SystemExit("Falta TELEGRAM_TOKEN nas env vars.")
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
                       text=f"Sistemas online. Sou o JARVIS de {DONO}, direto da nuvem. Pode falar.")
                    continue
                tg("sendChatAction", chat_id=chat, action="typing")
                tg("sendMessage", chat_id=chat, text=cerebro(chat, texto)[:4000])
        except Exception as e:
            log.warning(f"loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
