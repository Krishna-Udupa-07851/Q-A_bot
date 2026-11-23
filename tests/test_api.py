import io
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from src.app import app, store
from src.schemas import AskResponse


def make_pdf(pages_text: list[str]) -> bytes:
    """Helper to generate valid multi-page PDF bytes for tests."""
    objects = []
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    kids = " ".join(f"{3 + i*3} 0 R" for i in range(len(pages_text)))
    objects.append(f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {len(pages_text)} >>\nendobj\n".encode("latin1"))

    font_obj_num = 3 + len(pages_text) * 3
    for i, text in enumerate(pages_text):
        page_num = 3 + i * 3
        content_num = page_num + 1
        stream = f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode("latin1")
        objects.append(
            f"{page_num} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_num} 0 R /Resources << /Font << /F1 {font_obj_num} 0 R >> >> >>\nendobj\n".encode("latin1")
        )
        objects.append(
            f"{content_num} 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode("latin1") + stream + b"\nendstream\nendobj\n"
        )

    objects.append(f"{font_obj_num} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n".encode("latin1"))

    header = b"%PDF-1.4\n"
    body = b"".join(objects)
    trailer = b"trailer\n<< /Size 10 /Root 1 0 R >>\nstartxref\n9999\n%%EOF\n"
    return header + body + trailer


@pytest.fixture(autouse=True)
def reset_store():
    """Ensure in-memory store is reset before and after every test."""
    store.clear()
    yield
    store.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_root_status(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["has_document"] is False


def test_ask_before_upload_fails(client):
    response = client.post("/ask", json={"question": "What is the return window?"})
    assert response.status_code == 400
    assert "No document has been uploaded yet" in response.json()["detail"]


def test_upload_non_pdf_fails(client):
    response = client.post(
        "/documents",
        files={"file": ("test.txt", b"plain text", "text/plain")}
    )
    assert response.status_code == 400
    assert "Only PDF files are supported" in response.json()["detail"]


def test_upload_empty_file_fails(client):
    response = client.post(
        "/documents",
        files={"file": ("empty.pdf", b"", "application/pdf")}
    )
    assert response.status_code == 400
    assert "Uploaded file is empty" in response.json()["detail"]


def test_upload_scanned_or_no_text_pdf_refuses_cleanly(client):
    # Create a PDF with blank pages (no extractable text)
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    blank_pdf = buf.getvalue()

    response = client.post(
        "/documents",
        files={"file": ("scanned.pdf", blank_pdf, "application/pdf")}
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "No extractable text found in PDF" in detail or "Scanned" in detail


def test_upload_valid_pdf_succeeds(client):
    pdf_bytes = make_pdf([
        "Page 1: Standard delivery takes 3 to 5 business days.",
        "Page 2: Products can be returned within 30 days for a full refund."
    ])

    response = client.post(
        "/documents",
        files={"file": ("policy.pdf", pdf_bytes, "application/pdf")}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "policy.pdf"
    assert data["total_pages"] == 2
    assert data["total_passages"] >= 2
    assert store.has_document() is True


def test_ask_with_mocked_llm(client, monkeypatch):
    pdf_bytes = make_pdf([
        "Page 1: Standard delivery takes 3 to 5 business days.",
        "Page 2: Products can be returned within 30 days for a full refund."
    ])
    client.post("/documents", files={"file": ("policy.pdf", pdf_bytes, "application/pdf")})

    # Mock the LLM to verify retrieval and typed output without requiring network
    def mock_generate_answer(question, passages):
        assert len(passages) > 0
        # Check that retriever selected page 2 for return question
        if "return" in question.lower():
            assert any(p["page"] == 2 for p in passages)
            return AskResponse(answer="Products can be returned within 30 days.", page=2)
        elif "delivery" in question.lower():
            assert any(p["page"] == 1 for p in passages)
            return AskResponse(answer="Standard delivery takes 3 to 5 business days.", page=1)
        else:
            return AskResponse(
                answer="The provided document does not contain information to answer this question.",
                page=None
            )

    monkeypatch.setattr("src.app.generate_answer", mock_generate_answer)

    # 1. Ask about delivery -> citations should point to page 1
    resp1 = client.post("/ask", json={"question": "What is the delivery time?"})
    assert resp1.status_code == 200
    assert resp1.json()["page"] == 1
    assert "3 to 5 business days" in resp1.json()["answer"]

    # 2. Ask about returns -> citation should point to page 2
    resp2 = client.post("/ask", json={"question": "What is the return window?"})
    assert resp2.status_code == 200
    assert resp2.json()["page"] == 2
    assert "30 days" in resp2.json()["answer"]

    # 3. Ask about an unrelated topic -> no-answer case
    resp3 = client.post("/ask", json={"question": "What is the battery warranty?"})
    assert resp3.status_code == 200
    assert resp3.json()["page"] is None
    assert "does not contain information" in resp3.json()["answer"]


def test_clear_document(client):
    pdf_bytes = make_pdf(["Page 1: Some text"])
    client.post("/documents", files={"file": ("test.pdf", pdf_bytes, "application/pdf")})
    assert store.has_document() is True

    del_resp = client.delete("/documents")
    assert del_resp.status_code == 200
    assert store.has_document() is False

    ask_resp = client.post("/ask", json={"question": "Anything?"})
    assert ask_resp.status_code == 400


def test_live_groq_integration(client):
    """Live integration test against Groq model with honest citations."""
    import os
    if not os.getenv("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY is not set.")

    pdf_bytes = make_pdf([
        "Page 1: Standard delivery takes 3 to 5 business days.",
        "Page 2: Products can be returned within 30 days for a full refund."
    ])
    client.post("/documents", files={"file": ("sample_policy.pdf", pdf_bytes, "application/pdf")})

    # Test question answered by Page 1
    resp1 = client.post("/ask", json={"question": "What is the standard delivery time?"})
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["page"] == 1
    assert "3 to 5" in data1["answer"]

    # Test question answered by Page 2
    resp2 = client.post("/ask", json={"question": "How many days to return an item?"})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["page"] == 2
    assert "30" in data2["answer"]

    # Test question not covered in PDF
    resp3 = client.post("/ask", json={"question": "What is the capital of France?"})
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert data3["page"] is None
    assert "does not contain" in data3["answer"].lower()

