import io
from typing import List, Dict, Any
from pypdf import PdfReader


def extract_passages_from_pdf(file_bytes: bytes, max_words_per_passage: int = 150) -> List[Dict[str, Any]]:
    """
    Extracts text from a PDF file page by page and chunks it into passages.
    Each passage retains its 1-based page number.
    Raises ValueError if the PDF is empty or contains no extractable text (e.g. scanned).
    """
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"Invalid PDF file format: {str(e)}")

    if len(reader.pages) == 0:
        raise ValueError("PDF has 0 pages.")

    passages: List[Dict[str, Any]] = []
    total_characters = 0
    passage_id = 1

    for page_idx, page in enumerate(reader.pages):
        page_num = page_idx + 1
        page_text = page.extract_text() or ""
        page_text = page_text.strip()
        total_characters += len(page_text)

        if not page_text:
            continue

        # Split page text into paragraphs or chunks preserving page number
        paragraphs = [p.strip() for p in page_text.split("\n\n") if p.strip()]
        
        current_chunk_words: List[str] = []
        for paragraph in paragraphs:
            words = paragraph.split()
            if not words:
                continue

            # If current chunk + new paragraph exceeds max words, flush current chunk
            if len(current_chunk_words) + len(words) > max_words_per_passage and current_chunk_words:
                passages.append({
                    "id": passage_id,
                    "page": page_num,
                    "text": " ".join(current_chunk_words)
                })
                passage_id += 1
                current_chunk_words = []

            # If single paragraph is very long, break it into chunks of max_words_per_passage
            if len(words) > max_words_per_passage:
                for i in range(0, len(words), max_words_per_passage):
                    chunk = words[i:i + max_words_per_passage]
                    passages.append({
                        "id": passage_id,
                        "page": page_num,
                        "text": " ".join(chunk)
                    })
                    passage_id += 1
            else:
                current_chunk_words.extend(words)

        if current_chunk_words:
            passages.append({
                "id": passage_id,
                "page": page_num,
                "text": " ".join(current_chunk_words)
            })
            passage_id += 1

    # Check if any extractable text was found across all pages
    if total_characters == 0 or len(passages) == 0:
        raise ValueError("No extractable text found in PDF. Scanned or image-only documents cannot be processed.")

    return passages
