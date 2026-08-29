"""Thin wrapper around Google's Gemini API for embeddings + chat.

Uses the `google-genai` SDK (the current, recommended one — the older
`google-generativeai` package is legacy). Two model calls are used:

- gemini-embedding-001  -> turns text into a 768-dim vector for search
- gemini-2.5-flash      -> answers questions using retrieved resume chunks
                           (Flash, not Pro, since Pro models were removed
                           from the free tier in April 2026)
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
    """Embed a batch of texts. task_type is RETRIEVAL_DOCUMENT for resume
    chunks going into storage, and RETRIEVAL_QUERY for the user's search /
    chat question — Gemini's embedding model is asymmetric and tuned for
    that distinction, and using the right one measurably improves recall."""
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
    """Ask Gemini Flash to answer `question`, grounded only in the retrieved
    resume chunks. context_chunks: list of {company, role, resume_filename, content}.
    """
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
        "You are a helpful assistant that answers questions about the user's own "
        "job application history and resumes, based only on the resume excerpts "
        "provided as context. If the answer isn't in the context, say so plainly "
        "instead of guessing. Be concise and specific — mention which resume/company "
        "an answer comes from when relevant."
    )

    prompt = f"Context (excerpts from the user's resumes):\n\n{context_block}\n\nQuestion: {question}"

    response = client.models.generate_content(
        model=config.CHAT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2,
        ),
    )
    return response.text
