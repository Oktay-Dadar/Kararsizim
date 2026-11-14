import hashlib
import secrets
import string

from django.conf import settings

PUBLIC_ID_ALPHABET = string.ascii_letters + string.digits
PUBLIC_ID_LENGTH = 12

VOTER_TOKEN_SESSION_KEY = "voter_token"


def generate_public_id():
    return "".join(secrets.choice(PUBLIC_ID_ALPHABET) for _ in range(PUBLIC_ID_LENGTH))


def get_voter_key(request, create=False):
    """Hash of a random per-session token (docs/PROJECT.md §15 #4).

    The token lives in session data, so it survives the session-key rotation on login.
    It is only created when someone votes, so anonymous page views write nothing.
    """
    token = request.session.get(VOTER_TOKEN_SESSION_KEY)
    if not token:
        if not create:
            return None
        token = secrets.token_urlsafe(32)
        request.session[VOTER_TOKEN_SESSION_KEY] = token
    return hashlib.sha256(f"{token}{settings.VOTER_KEY_SALT}".encode()).hexdigest()
