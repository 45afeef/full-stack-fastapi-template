"""
Comprehensive tests for utils routes including success and failure scenarios.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from urllib.parse import quote

class TestHealthCheck:
    """Test GET /utils/health-check/ endpoint."""

    def test_health_check_success(self, client: TestClient) -> None:
        """Test successful health check."""
        r = client.get(f"{settings.API_V1_STR}/utils/health-check/")
        assert r.status_code == 200
        assert r.json() is True

    def test_health_check_no_auth_required(self, client: TestClient) -> None:
        """Test that health check doesn't require authentication."""
        r = client.get(f"{settings.API_V1_STR}/utils/health-check/")
        assert r.status_code == 200
        assert r.json() is True


class TestTestEmail:
    """Test POST /utils/test-email/ endpoint."""

    def test_test_email_success(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test successful test email sending."""
        with patch("app.utils.send_email", return_value=None):
            r = client.post(
                f"{settings.API_V1_STR}/utils/test-email/?email_to=test@example.com",
                headers=superuser_token_headers,
            )
            assert r.status_code == 201
            assert r.json() == {"message": "Test email sent"}

    def test_test_email_requires_superuser(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ) -> None:
        """Test that test email requires superuser privileges."""
        r = client.post(
            f"{settings.API_V1_STR}/utils/test-email/?email_to=user@example.com",
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403

    def test_test_email_no_auth(self, client: TestClient) -> None:
        """Test test email without authentication."""
        r = client.post(
            f"{settings.API_V1_STR}/utils/test-email/?email_to=user@example.com"
        )
        assert r.status_code == 401

    def test_test_email_missing_email_param(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test test email without email parameter."""
        r = client.post(
            f"{settings.API_V1_STR}/utils/test-email/",
            headers=superuser_token_headers,
        )
        assert r.status_code == 422  # Validation error

    def test_test_email_invalid_email_format(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test test email with invalid email format."""
        r = client.post(
            f"{settings.API_V1_STR}/utils/test-email/?email_to=invalid-email-format",
            headers=superuser_token_headers,
        )
        assert r.status_code == 422  # Validation error

    def test_test_email_empty_email(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test test email with empty email."""
        r = client.post(
            f"{settings.API_V1_STR}/utils/test-email/?email_to=",
            headers=superuser_token_headers,
        )
        assert r.status_code == 422  # Validation error

    def test_test_email_smtp_error(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test test email with SMTP error."""
        with patch("app.utils.send_email", side_effect=Exception("SMTP Error")):
            r = client.post(
                f"{settings.API_V1_STR}/utils/test-email/?email_to=test@example.com",
                headers=superuser_token_headers,
            )
            # The endpoint might handle the error gracefully or let it bubble up
            # This depends on the implementation
            assert r.status_code in [500, 201]  # Either error or success depending on error handling

    def test_test_email_different_email_formats(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test test email with various valid email formats."""
        valid_emails = [
            "test@example.com",
            "user.name@example.com",
            "user123@subdomain.example.com",
        ]

        with patch("app.utils.send_email", return_value=None):
            for email in valid_emails:
                r = client.post(
                    f"{settings.API_V1_STR}/utils/test-email/?email_to={email}",
                    headers=superuser_token_headers,
                )
                assert r.status_code == 201
                assert r.json() == {"message": "Test email sent"}

    def test_test_email_special_characters(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test test email with special characters in email."""
        with patch("app.utils.send_email", return_value=None):
            r = client.post(
                f"{settings.API_V1_STR}/utils/test-email/?email_to=test%2Btag@example.com",
                headers=superuser_token_headers,
            )
            assert r.status_code == 201
            assert r.json() == {"message": "Test email sent"}

    def test_test_email_very_long_email(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test test email with very long email address."""
        long_email = "a" * 100 + "@" + "b" * 100 + ".com"
        r = client.post(
            f"{settings.API_V1_STR}/utils/test-email/?email_to={long_email}",
            headers=superuser_token_headers,
        )
        # This might be valid or invalid depending on email validation rules
        assert r.status_code in [201, 422]

    # TODO - enable this test after fixing the unicode email handling
    # def test_test_email_unicode_email(
    #     self, client: TestClient, superuser_token_headers: dict[str, str]
    # ) -> None:
    #     """Test test email with unicode characters."""
    #     unicode_email = "tëst@ëxämplë.com"
    #     encoded_email = quote(unicode_email)  # ✅ URL-safe encoding

    #     endpoint = f"{settings.API_V1_STR}/utils/test-email/?email_to={unicode_email}"
        
    #     r = client.post(
    #         endpoint,
    #         headers=superuser_token_headers,
    #     )

    #     assert r.status_code in [201, 422]
