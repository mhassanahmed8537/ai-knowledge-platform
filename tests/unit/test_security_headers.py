from fastapi.testclient import TestClient

from api.main import app


def test_security_headers_present_on_every_response() -> None:
    client = TestClient(app)
    response = client.get("/healthz")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_hsts_omitted_in_local_dev() -> None:
    # The test app runs with the default ENVIRONMENT=local; HSTS is only
    # meaningful (and only sent) once TLS is actually in front of it.
    client = TestClient(app)
    response = client.get("/healthz")
    assert "Strict-Transport-Security" not in response.headers


def test_docs_available_in_local_dev() -> None:
    client = TestClient(app)
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
