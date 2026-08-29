"""RAG orchestration: ties retrieval (resumes_db) and generation (gemini_client)
together for the chat tab. Kept as its own thin module so app.py stays UI-only.
"""

import resumes_db
import gemini_client


def ask(question: str, match_count: int = 5) -> dict:
    """Runs the full RAG loop for one question. Returns the answer plus the
    source chunks used, so the UI can show 'grounded in these resumes'."""
    chunks = resumes_db.search_similar_chunks(question, match_count=match_count)
    answer = gemini_client.answer_with_context(question, chunks)
    return {"answer": answer, "sources": chunks}
