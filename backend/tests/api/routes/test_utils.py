from fastapi.testclient import TestClient

from app.core.config import settings


def test_health_check(client: TestClient) -> None:
    r = client.get(f"{settings.API_V1_STR}/utils/health-check/")
    assert r.status_code == 200
    assert r.json() is True


def test_test_email_requires_superuser(client: TestClient, normal_user_token_headers: dict[str, str]) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/utils/test-email/?email_to=user@example.com",
        headers=normal_user_token_headers,
    )
    assert r.status_code in (401, 403)


def test_test_email_superuser(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/utils/test-email/?email_to=test@example.com",
        headers=superuser_token_headers,
    )
    assert r.status_code == 201
    assert r.json() == {"message": "Test email sent"}


