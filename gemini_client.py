"""Thin wrapper around Google's Gemini API for embeddings + chat.

Uses the `google-genai` SDK. Two model calls are used:
- gemini-embedding-001 -> turns text into a 768-dim vector for search
- gemini-2.5-flash / gemini-1.5-flash -> answers questions using retrieved resume chunks
"""

from functools import lru_cache

from google import genai
from google.genai import types

import config


@lru_cache(maxsize=1)
def get_client() -> genai.Client:
    if not config.GEMINI_API_KEY:
        raise RuntimeError(
            "Gemini is not configured. Set GEMINI_API_KEY (get a free key at "
            "https://aistudio.google.com/apikey)."
        )
    return genai.Client(api_key=config.GEMINI_API_KEY)


def embed_texts(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Embed a batch of texts using Gemini's asymmetric task types."""
    if not texts:
        return []
    client = get_client()
    result = client.models.embed_content(
        model=config.EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            output_dimensionality=config.EMBEDDING_DIM,
            task_type=task_type,
        ),
    )
    return [e.values for e in result.embeddings]


def embed_query(text: str) -> list[float]:
    return embed_texts([text], task_type="RETRIEVAL_QUERY")[0]


def answer_with_context(question: str, context_chunks: list[dict]) -> str:
    """Ask Gemini Flash to answer `question`, grounded only in the retrieved resume chunks."""
    client = get_client()

    if not context_chunks:
        context_block = "(No matching resume content was found for this question.)"
    else:
        parts = []
        for c in context_chunks:
            header = f"[Resume: {c.get('resume_filename', 'unknown')} | Company: {c.get('company', '?')} | Role: {c.get('role', '?')}]"
            parts.append(f"{header}\n{c['content']}")
        context_block = "\n\n---\n\n".join(parts)

    system_instruction = (
        "You are a helpful AI assistant for a Job Tracker app. Your job is to answer questions "
        "about the user's job application history and resumes based strictly on the provided context excerpts.\n"
        "- Be concise, accurate, and professional.\n"
        "- Always cite which company, role, or resume file an answer comes from when available.\n"
        "- If the context doesn't contain enough information to answer, state clearly that the information isn't present in the uploaded resumes."
    )

    prompt = f"Context (excerpts from user resumes):\n\n{context_block}\n\nUser Question: {question}"

    models_to_try = [config.CHAT_MODEL, "gemini-2.5-flash", "gemini-1.5-flash"]
    last_err = None

    for model_name in dict.fromkeys(models_to_try):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2,
                ),
            )
            return response.text
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"Gemini API call failed with error: {last_err}")
