# models.py — Vertex AI (Gemini 2.5) via LangChain
import os
from langchain_google_vertexai import ChatVertexAI

PROJECT_ID = "cbldt-b016-int-2e05"
LOCATION = os.environ.get("VERTEX_LOCATION", "us-central1")
API_ENDPOINT = os.environ.get("VERTEX_API_ENDPOINT", f"{LOCATION}-aiplatform.googleapis.com")


def _chat(
    model_name: str, temperature: float, max_tokens: int, timeout_s: int, thinking_budget: int = 8192
) -> ChatVertexAI:
    return ChatVertexAI(
        model_name=model_name,
        project=PROJECT_ID,
        location=LOCATION,
        api_endpoint=API_ENDPOINT,
        temperature=temperature,
        max_output_tokens=max_tokens,
        max_retries=2,
        timeout=timeout_s,
        model_kwargs={
            "thinking_config": {"thinking_budget": thinking_budget},
        },
    )


# Fast/tiny — small budget or disable thinking entirely
llm_fast = _chat("gemini-2.5-flash", 0.2, 256, 30, thinking_budget=0)

# Medium — modest thinking
llm_medium = _chat("gemini-2.5-flash", 0.5, 2048, 60, thinking_budget=2048)

# Respond — full thinking
llm_respond = _chat("gemini-2.5-pro", 0.7, 2048, 180, thinking_budget=8192)

# Large — maximum thinking budget
llm_large = _chat("gemini-2.5-pro", 0.7, 4096, 240, thinking_budget=16384)
