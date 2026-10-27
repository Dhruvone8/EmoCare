from datetime import datetime, timedelta, timezone

import jwt

TEST_SUPABASE_URL = "https://test-project.supabase.co"
TEST_SUPABASE_SECRET = "test-supabase-secret-with-at-least-32-bytes"
TEST_GUEST_SECRET = "test-guest-secret-with-at-least-32-bytes"


def make_supabase_token(
    user_id: str,
    expires_delta: timedelta = timedelta(hours=1),
    secret: str = TEST_SUPABASE_SECRET,
) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user_id,
            "email": f"{user_id}@example.test",
            "iat": now,
            "exp": now + expires_delta,
            "iss": f"{TEST_SUPABASE_URL}/auth/v1",
            "aud": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def make_guest_token(
    user_id: str,
    expires_delta: timedelta = timedelta(hours=1),
    secret: str = TEST_GUEST_SECRET,
) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user_id,
            "iat": now,
            "exp": now + expires_delta,
            "iss": "emocare",
            "aud": "emocare-guest",
            "token_type": "guest",
        },
        secret,
        algorithm="HS256",
    )


def auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_supabase_token(user_id)}"}
