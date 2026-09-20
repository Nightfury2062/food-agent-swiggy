import os
import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel

load_dotenv()

BASE_URL = os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY", "local")
SMART = os.getenv("SMART_MODEL") or os.getenv("MODEL", "gemini-3.5-flash-lite")
FAST = os.getenv("FAST_MODEL") or SMART

usage_log: list[dict] = []   # raw `usage` object from every model response


async def _capture_usage(resp: httpx.Response):
    if resp.request.url.path.endswith("/chat/completions"):
        await resp.aread()
        try:
            usage_log.append(resp.json().get("usage") or {})
        except Exception:
            pass


def _make_client(base_url, api_key):
    return AsyncOpenAI(
        api_key=api_key, base_url=base_url, max_retries=6,
        http_client=httpx.AsyncClient(timeout=90, event_hooks={"response": [_capture_usage]}),
    )


client = _make_client(BASE_URL, API_KEY)
# Optional: serve the cheap "fast" role from a local model (Ollama, llama.cpp, vLLM)
_fast_client = _make_client(os.environ["FAST_BASE_URL"], "local") if os.getenv("FAST_BASE_URL") else client


def get_model(role: str = "smart") -> OpenAIChatCompletionsModel:
    if role == "fast":
        return OpenAIChatCompletionsModel(model=FAST, openai_client=_fast_client)
    return OpenAIChatCompletionsModel(model=SMART, openai_client=client)


def usage_summary() -> dict:
    cached = sum(((u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0) for u in usage_log)
    return {
        "calls": len(usage_log),
        "prompt": sum(u.get("prompt_tokens", 0) for u in usage_log),
        "completion": sum(u.get("completion_tokens", 0) for u in usage_log),
        "cached": cached,
    }