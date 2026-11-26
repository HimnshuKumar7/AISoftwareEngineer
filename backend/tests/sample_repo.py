"""A small in-memory 'repository' used by RAG tests."""
from typing import Dict, Tuple

from app.ingestion.chunker import chunk_files
from app.ingestion.index_store import RepoVectorIndex

SLUGIFY = '''def slugify(value):
    """Turn a title into a URL slug."""
    value = value.strip().lower()
    out = []
    for ch in value:
        if ch.isalnum():
            out.append(ch)
        elif ch in " -_":
            out.append("-")
    slug = "".join(out)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")
'''

FILES: Dict[str, str] = {
    "auth/jwt_utils.py": '''import time
import jwt

SECRET = "x"


def create_token(user_id, ttl=3600):
    """Create a signed JWT access token for the user."""
    payload = {"sub": str(user_id), "exp": int(time.time()) + ttl}
    return jwt.encode(payload, SECRET, algorithm="HS256")


def verify_token(token):
    """Verify the JWT signature and expiry; return the user id or None."""
    try:
        data = jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return data.get("sub")
''',
    "db/session.py": '''import sqlite3


def get_connection(path):
    """Open a database connection with foreign keys enabled."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def close_connection(conn):
    """Commit and close the database connection."""
    conn.commit()
    conn.close()
''',
    "utils/strings.py": SLUGIFY + '''

def truncate(text, limit=80):
    """Shorten text to the limit and add an ellipsis."""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
''',
    "utils/text.py": SLUGIFY.replace("slugify", "slugify"),  # exact copy -> exact duplicate
    "utils/slugs.py": SLUGIFY.replace("def slugify(value)", "def make_slug(title)").replace("value", "title"),  # near duplicate
    "api/users.py": '''class UserService:
    """CRUD operations for users."""

    def __init__(self, db):
        self.db = db

    def get_user(self, user_id):
        """Fetch a single user by id from the database."""
        cur = self.db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return cur.fetchone()

    def delete_user(self, user_id):
        """Delete a user and all their sessions."""
        self.db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        self.db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.db.commit()
''',
    "README.md": "# Sample\n\nThis sample service handles authentication with JWT tokens and stores users in a database.\n",
}


def build_index(embedder) -> Tuple[RepoVectorIndex, list]:
    chunks = list(chunk_files(((p, s.encode()) for p, s in FILES.items()), max_lines=60))
    vecs = embedder.encode([c.embedding_text() for c in chunks])
    return RepoVectorIndex.build(vecs, chunks), chunks
