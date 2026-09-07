import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import httpx
from src.config import settings

def test_groq():
    print("\n[1/4] Testing Groq...")
    if not settings.GROQ_API_KEY or "your_" in settings.GROQ_API_KEY:
        print("  SKIPPED: GROQ_API_KEY not configured.")
        return False
    try:
        from groq import Groq
        client = Groq(api_key=settings.GROQ_API_KEY)
        completion = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[
                {"role": "system", "content": "You are a concise emergency triage assistant."},
                {"role": "user", "content": "Respond with 'GROQ_OK' only."}
            ],
            temperature=0.1,
            max_tokens=15,
        )
        reply = completion.choices[0].message.content.strip()
        print(f"  SUCCESS! Model: qwen/qwen3.6-27b | Response: {reply}")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

def test_gemini():
    print("\n[2/4] Testing Google Gemini...")
    if not settings.GEMINI_API_KEY or "your_" in settings.GEMINI_API_KEY:
        print("  SKIPPED: GEMINI_API_KEY not configured.")
        return False
    try:
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents="Respond with 'GEMINI_OK' only.",
        )
        reply = response.text.strip()
        print(f"  SUCCESS! Model: gemini-3.6-flash | Response: {reply}")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

def test_openrouter():
    print("\n[3/4] Testing OpenRouter...")
    if not settings.OPENROUTER_API_KEY or "your_" in settings.OPENROUTER_API_KEY:
        print("  SKIPPED: OPENROUTER_API_KEY not configured.")
        return False
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://github.com/golden-dispatch",
            "X-Title": "GOLDEN Emergency Dispatch",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "nvidia/nemotron-3.5-lightning:free",
            "messages": [
                {"role": "user", "content": "Respond with 'OPENROUTER_OK' only."}
            ],
            "max_tokens": 15
        }
        with httpx.Client(timeout=25.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                reply = data["choices"][0]["message"]["content"].strip()
                print(f"  SUCCESS! Model: nvidia/nemotron-3.5-lightning:free | Response: {reply}")
                return True
            else:
                print(f"  HTTP {resp.status_code}: {resp.text}")
                return False
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

def test_ollama():
    print("\n[4/4] Testing Ollama Local (qwen2.5:7b)...")
    try:
        url = f"{settings.OLLAMA_HOST}/api/generate"
        payload = {
            "model": settings.OLLAMA_MODEL,
            "prompt": "Respond with 'OLLAMA_OK' only.",
            "stream": False
        }
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                reply = data.get("response", "").strip()
                print(f"  SUCCESS! Model: {settings.OLLAMA_MODEL} | Response: {reply}")
                return True
            else:
                print(f"  Ollama returned HTTP {resp.status_code}: {resp.text}")
                return False
    except Exception as e:
        print(f"  FAILED: Could not reach Ollama at {settings.OLLAMA_HOST} ({e})")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("GOLDEN: LLM Providers Smoke Test")
    print("=" * 60)
    r1 = test_groq()
    r2 = test_gemini()
    r3 = test_openrouter()
    r4 = test_ollama()
    print("\n" + "=" * 60)
    print(f"Summary: Groq={r1}, Gemini={r2}, OpenRouter={r3}, Ollama={r4}")
    print("=" * 60)
