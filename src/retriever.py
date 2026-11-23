import re
from typing import List, Dict, Any, Optional

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", 
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", 
    "by", "can", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", 
    "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", 
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", 
    "me", "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once", 
    "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own", "same", "she", 
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves", 
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", 
    "up", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom", 
    "why", "with", "would", "you", "your", "yours", "yourself", "yourselves"
}


def tokenize(text: str) -> List[str]:
    """Extract lowercased alphanumeric words from text."""
    return re.findall(r"\b[a-z0-9]+\b", text.lower())


class DocumentStore:
    """
    In-memory storage and word-overlap retriever for document passages.
    """
    def __init__(self):
        self.filename: Optional[str] = None
        self.passages: List[Dict[str, Any]] = []

    def set_document(self, filename: str, passages: List[Dict[str, Any]]) -> None:
        self.filename = filename
        self.passages = passages

    def clear(self) -> None:
        self.filename = None
        self.passages = []

    def has_document(self) -> bool:
        return len(self.passages) > 0

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieves top_k passages using word overlap scoring.
        """
        if not self.passages:
            return []

        query_tokens = [t for t in tokenize(query) if t not in STOPWORDS]
        if not query_tokens:
            # If all query words were stopwords, fallback to full token list
            query_tokens = tokenize(query)

        if not query_tokens:
            return self.passages[:top_k]

        query_set = set(query_tokens)
        scored_passages = []

        for p in self.passages:
            p_tokens = tokenize(p["text"])
            if not p_tokens:
                continue

            # Score based on unique matched query tokens + token frequency
            matched_unique = query_set.intersection(p_tokens)
            score = len(matched_unique) * 2.0
            for t in p_tokens:
                if t in query_set:
                    score += 0.5

            if score > 0:
                scored_passages.append((score, p))

        # Sort by score descending
        scored_passages.sort(key=lambda x: x[0], reverse=True)

        if scored_passages:
            return [p for _, p in scored_passages[:top_k]]
        
        # If no explicit keyword overlap found, return top passages as fallback context
        return self.passages[:top_k]
