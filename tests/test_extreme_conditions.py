import io
from fastapi.testclient import TestClient
from app.main import app as fastapi_app
from app.orchestration.pipeline import MAX_CSV_COLUMNS, MAX_CSV_ROWS

client = TestClient(fastapi_app)

def test_extreme_column_limit():
    """Test #1: Pipeline rejects files with too many columns."""
    # Create a CSV header with MAX_CSV_COLUMNS + 1 columns
    cols = ",".join([f"col_{i}" for i in range(MAX_CSV_COLUMNS + 1)])
    csv_content = f"{cols}\n" + ",".join(["1"] * (MAX_CSV_COLUMNS + 1)) + "\n"
    file_obj = io.BytesIO(csv_content.encode("utf-8"))
    
    # Using 50MB content-length to simulate normal upload but large columns
    response = client.post(
        "/pipeline/upload", 
        files={"file": ("extreme_cols.csv", file_obj, "text/csv")}
    )
    
    # Should be rejected
    assert response.status_code == 400
    assert "exceeding the maximum" in response.json()["detail"] or "columns" in response.json()["detail"]

def test_extreme_size_limit():
    """Test #2: Pipeline rejects files over the size limit."""
    # Create a very large file object without using much memory by using a huge content-length header
    # But since FastAPI reads it, we just create a file slightly over 50MB
    # Wait, creating 50MB string is 50MB RAM, fine for a test runner.
    # Let's just pass a content length header to trigger the 413.
    response = client.post(
        "/pipeline/upload",
        files={"file": ("large.csv", io.BytesIO(b"id,val\n1,2\n"), "text/csv")},
        headers={"content-length": str(60 * 1024 * 1024)}  # 60MB
    )
    # The RequestSizeLimitMiddleware should block this
    assert response.status_code == 413

def test_invalid_utf8_binary_bomb():
    """Test #3: Pipeline rejects non-CSV binary data safely without crashing."""
    binary_data = bytes([0x80, 0x81, 0x82, 0x83] * 1000)
    file_obj = io.BytesIO(binary_data)
    response = client.post(
        "/pipeline/upload",
        files={"file": ("bomb.csv", file_obj, "text/csv")}
    )
    assert response.status_code == 400
    assert "valid UTF-8" in response.json()["detail"]
