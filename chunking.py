"""Split extracted resume text into overlapping chunks for embedding.

Resumes are short (typically 300-1000 words), so chunking is lighter-weight
than a typical long-document RAG pipeline: a resume section (e.g. "Experience
at Company X") is what we want each chunk to roughly capture, so we split on
paragraph/section boundaries first and only fall back to hard character
splits for unusually long single paragraphs.
"""

import config


def chunk_text(
    text: str,
    chunk_size: int = config.CHUNK_SIZE_CHARS,
    overlap: int = config.CHUNK_OVERLAP_CHARS,
) -> list[str]:
    text = text.strip()
    if not text:
        return []

    # Split on blank lines / section breaks first
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) <= 1:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        candidate = (current + "\n\n" + para).strip() if current else para
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if len(para) > chunk_size:
                # Single paragraph too long on its own — hard split with overlap
                chunks.extend(_hard_split(para, chunk_size, overlap))
                current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    # Apply overlap between adjacent chunks so context isn't lost at boundaries
    if overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-overlap:]
            overlapped.append((prev_tail + "\n\n" + chunks[i]).strip())
        chunks = overlapped

    return chunks


def _hard_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    step = max(chunk_size - overlap, 1)
    return [text[i : i + chunk_size] for i in range(0, len(text), step)]
