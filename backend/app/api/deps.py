from __future__ import annotations

import uuid
from typing import Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import AuthError, NotFoundError
from app.core.security import decode_access_token
from app.db.models import Repository, User
from app.db.session import get_db

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer), db: Session = Depends(get_db)
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise AuthError("Authentication required")
    user_id = decode_access_token(creds.credentials)
    if user_id is None:
        raise AuthError("Invalid or expired token")
    user = db.get(User, user_id)
    if user is None:
        raise AuthError("Invalid or expired token")
    return user


def get_owned_repo(repo_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Repository:
    """Authorization: a repository is only reachable by its owner. Others get 404 (no existence leak)."""
    repo = db.get(Repository, repo_id)
    if repo is None or repo.user_id != user.id:
        raise NotFoundError("Repository not found")
    return repo
