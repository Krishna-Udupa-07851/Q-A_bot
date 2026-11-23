import os
import json
import logging
from typing import List, Dict, Any, Optional
from groq import Groq
from dotenv import load_dotenv

from .schemas import AskResponse

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")


def get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is not set.")
    return Groq(api_key=api_key)


SYSTEM_PROMPT = """You are a strictly factual Document Q&A assistant.
You must answer the user's question using ONLY the provided text passages.
Each passage is explicitly labeled with its honest source page number.

Rules:
1. If the provided context contains the answer, write a concise, direct answer and set "page" to the exact 1-based integer page number where the answer was found.
2. If the provided context does NOT contain enough information to answer the question, set "answer" to "The provided document does not contain information to answer this question." and set "page" to null.
3. NEVER invent answers, assume facts outside the text, or guess page numbers.
4. Output strictly valid JSON matching:
{
  "answer": "string",
  "page": integer_or_null
}
"""


def generate_answer(
    question: str, 
    passages: List[Dict[str, Any]], 
    model: str = DEFAULT_MODEL
) -> AskResponse:
    """
    Calls the LLM with the question and retrieved passages, returning a typed AskResponse.
    """
    if not passages:
        return AskResponse(
            answer="The provided document does not contain information to answer this question.",
            page=None
        )

    # Format context passages with page labels
    context_blocks = []
    for i, p in enumerate(passages, 1):
        context_blocks.append(f"--- Passage {i} (Page {p['page']}) ---\n{p['text']}")
    context_str = "\n\n".join(context_blocks)

    user_prompt = f"Context Passages:\n{context_str}\n\nQuestion: {question}\n\nProvide your response in JSON format."

    client = get_groq_client()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)

        answer_text = data.get("answer", "No answer could be extracted.")
        page_num: Optional[int] = data.get("page")

        # Basic sanity check on page number
        if page_num is not None:
            try:
                page_num = int(page_num)
            except (ValueError, TypeError):
                page_num = None

        return AskResponse(answer=answer_text, page=page_num)

    except Exception as e:
        logger.error(f"Error calling LLM: {e}")
        # Fallback cleanly rather than crashing
        return AskResponse(
            answer=f"Error generating answer: {str(e)}",
            page=None
        )
