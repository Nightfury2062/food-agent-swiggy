import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel, set_tracing_disabled

load_dotenv()

#temp
key = os.environ["GEMINI_API_KEY"]
print("Gemini key:", key[:8] + "..." + key[-4:])
print("Gemini model:", os.getenv("MODEL"))

# The SDK uploads traces to OpenAI by default, which needs an OpenAI key.
set_tracing_disabled(True)

client = AsyncOpenAI(
    api_key=os.environ["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    max_retries = 6,
)


def get_model() -> OpenAIChatCompletionsModel:
    return OpenAIChatCompletionsModel(
        model=os.getenv("MODEL", "gemini-2.5-flash"),
        openai_client=client,
    )