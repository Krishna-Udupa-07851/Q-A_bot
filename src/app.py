import os
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from dotenv import load_dotenv

from .schemas import DocumentResponse, AskRequest, AskResponse
from .pdf_processor import extract_passages_from_pdf
from .retriever import DocumentStore
from .llm import generate_answer

load_dotenv()

app = FastAPI(
    title="Document Q&A API",
    description="A simple, production-ready FastAPI service to ingest PDF documents and answer questions with honest page citations.",
    version="1.0.0"
)

# In-memory document passage store
store = DocumentStore()


@app.get("/health", tags=["Health"])
def health():
    return {
        "status": "online",
        "service": "Document Q&A API",
        "has_document": store.has_document(),
        "current_document": store.filename,
        "total_passages": len(store.passages)
    }


@app.post(
    "/documents", 
    response_model=DocumentResponse, 
    status_code=status.HTTP_201_CREATED,
    tags=["Documents"],
    summary="Upload and ingest a PDF document"
)
async def upload_document(file: UploadFile = File(...)):
    """
    Accepts a PDF file, extracts page-by-page text, and chunks it into indexed passages.
    Refuses scanned or empty PDFs cleanly with HTTP 400.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported. Please upload a valid .pdf file."
        )

    try:
        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes)."
            )

        passages = extract_passages_from_pdf(content)
        
        # Calculate distinct pages
        pages_detected = len(set(p["page"] for p in passages))
        store.set_document(file.filename, passages)

        return DocumentResponse(
            message="Document successfully processed and indexed.",
            filename=file.filename,
            total_pages=pages_detected,
            total_passages=len(passages)
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the document: {str(e)}"
        )


@app.post(
    "/ask", 
    response_model=AskResponse, 
    status_code=status.HTTP_200_OK,
    tags=["Q&A"],
    summary="Ask a question about the uploaded document"
)
async def ask_question(request: AskRequest):
    """
    Takes a plain language question, retrieves relevant passages, and returns a typed answer with the page citation.
    """
    if not store.has_document():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No document has been uploaded yet. Please upload a PDF first via POST /documents."
        )

    question = request.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty."
        )

    # 1. Retrieve top relevant passages
    top_passages = store.retrieve(question, top_k=3)

    # 2. Call LLM to generate answer with honest citation
    response = generate_answer(question, top_passages)

    return response


@app.delete(
    "/documents", 
    tags=["Documents"],
    summary="Clear the current document from memory"
)
async def clear_document():
    store.clear()
    return {"message": "Active document cleared successfully."}
