# Document Q&A API

A lightweight, production-grade FastAPI microservice that allows you to upload a PDF once and query it multiple times with honest page citations.

Designed for customer support and operations teams who need verifiable answers without skimming 20-page policy documents.

---

## Features

- **Upload Once, Ask Many Times**: Ingests PDF text once, chunks into indexed passages, and handles queries cheaply.
- **Honest Citations**: Every answer returns the exact 1-based page number where the fact was located.
- **Strictly Typed Response**: Outputs structured JSON (`{"answer": "...", "page": ...}`) via Pydantic models.
- **Clean Refusal**: Refuses scanned/image-only PDFs with clear HTTP 400 messages, and returns `page: null` when a question isn't covered in the text.
- **Zero Heavy Dependencies**: Uses pure Python `pypdf` and a fast word-overlap retriever.
- **Dockerized**: Ready to run with `docker compose up`.

---

## Project Structure

```
month_1_project/
├── src/
│   ├── app.py            # FastAPI endpoints & application lifecycle
│   ├── schemas.py        # Pydantic request and response schemas
│   ├── pdf_processor.py  # Text extraction and page-aware chunking
│   ├── retriever.py      # In-memory document store & word overlap retriever
│   └── llm.py            # Groq API client with structured citation prompting
├── tests/
│   └── test_api.py       # Full test suite (empty PDF, refusal, citations)
├── sample_policy.pdf     # 2-page sample PDF for quick testing
├── requirements.txt      # Python dependencies
├── Dockerfile            # Container definition
├── docker-compose.yml    # Docker Compose configuration
└── README.md
```

---

## Quickstart (Under 5 Minutes)

### 1. Clone & Set Environment

```bash
git clone <repo-url>
cd "Q&A_bot"

# Copy your Groq API key into .env
echo GROQ_API_KEY="your_groq_api_key_here" > .env
```

### 2. Run with Python Virtual Environment

```bash
# Create and activate virtual environment
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
```

The service is now live at: **`http://localhost:8000`**  
Interactive Swagger API docs: **`http://localhost:8000/docs`**

---

### 3. Or Run with Docker Compose

```bash
# Start container
docker compose up --build -d

# View logs
docker compose logs -f
```

---

## Usage Examples

### 1. Ingest a PDF (`POST /documents`)

```bash
curl -X POST "http://localhost:8000/documents" \
  -H "accept: application/json" \
  -F "file=@sample_policy.pdf;type=application/pdf"
```

**Response (`201 Created`):**
```json
{
  "message": "Document successfully processed and indexed.",
  "filename": "sample_policy.pdf",
  "total_pages": 2,
  "total_passages": 2
}
```

---

### 2. Ask a Question with Honest Citation (`POST /ask`)

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the standard delivery time?"}'
```

**Response (`200 OK`):**
```json
{
  "answer": "3 to 5 business days.",
  "page": 1
}
```

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "How many days do I have to return an item?"}'
```

**Response (`200 OK`):**
```json
{
  "answer": "30 days",
  "page": 2
}
```

---

### 3. Clean Refusal for Uncovered Questions

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the battery warranty duration?"}'
```

**Response (`200 OK`):**
```json
{
  "answer": "The provided document does not contain information to answer this question.",
  "page": null
}
```

---

### 4. Clean Refusal for Scanned / Empty PDFs

Uploading a blank or scanned PDF without extractable text:

**Response (`400 Bad Request`):**
```json
{
  "detail": "No extractable text found in PDF. Scanned or image-only documents cannot be processed."
}
```

---

## Running Automated Tests

Run the complete test suite with `pytest`:

```bash
pytest -v
```

All 9 tests verify:
- Health check status
- Asking before uploading (400 validation error)
- Non-PDF and empty (0-byte) rejection
- Scanned / blank PDF refusal
- Valid upload and passage indexing
- Citation verification (Page 1 vs Page 2)
- Clean refusal for out-of-scope questions
- Live Groq API integration
