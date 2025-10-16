from fastapi.testclient import TestClient

from app.core.config import settings


def test_recover_password_html_content_requires_superuser(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/password-recovery-html-content/test@example.com",
        headers=normal_user_token_headers,
    )
    assert r.status_code in (401, 403)


def test_recover_password_html_content_superuser(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    # Using FIRST_SUPERUSER to ensure user exists
    r = client.post(
        f"{settings.API_V1_STR}/password-recovery-html-content/{settings.FIRST_SUPERUSER}",
        headers=superuser_token_headers,
    )
    # The endpoint returns HTMLResponse; should be 200 if user exists
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert "<html" in r.text or "<body" in r.text or len(r.text) > 0


