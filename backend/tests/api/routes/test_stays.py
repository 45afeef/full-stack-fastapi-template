import uuid

from fastapi.testclient import TestClient

from app.core.config import settings


def test_list_units_requires_agency_or_superuser(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/stays/units",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "Not authorized to query stay units"


def test_list_units_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/stays/units",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    payload = r.json()
    assert "data" in payload and "count" in payload
    assert isinstance(payload["data"], list)
    assert isinstance(payload["count"], int)


def test_create_agency_requires_superuser(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/stays/agencies",
        headers=normal_user_token_headers,
        json={"name": "ACME Travel", "created_by": str(uuid.uuid4())},
    )
    assert r.status_code in (401, 403)


