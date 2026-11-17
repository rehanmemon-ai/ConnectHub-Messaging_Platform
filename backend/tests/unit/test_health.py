from fastapi.testclient import TestClient

import app.main as main_module


def test_liveness_does_not_require_database() -> None:
    with TestClient(main_module.app) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
    assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert response.headers["Cross-Origin-Resource-Policy"] == "same-origin"


def test_readiness_is_safe_when_database_is_unavailable(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def unavailable() -> bool:
        return False

    monkeypatch.setattr(main_module, "check_database_readiness", unavailable)
    with TestClient(main_module.app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}


def test_production_responses_include_hsts_and_csp(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(main_module.settings, "app_env", "production")
    with TestClient(main_module.app) as client:
        response = client.get("/health/live")

    assert response.headers["Strict-Transport-Security"] == ("max-age=31536000; includeSubDomains")
    policy = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "connect-src 'self'" in policy
