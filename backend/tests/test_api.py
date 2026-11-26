"""HTTP API tests (SQLite in tests; same SQLAlchemy models as Neon PostgreSQL)."""
import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.errors import ValidationFailure
from app.db.models import Repository, RepoIndex, QueryHistory
from app.db.session import session_scope
from app.ingestion.github import clone_repo, parse_github_url
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def patch_llm(monkeypatch, scripted_llm):
    monkeypatch.setattr("app.services.query_service.get_llm", lambda provider=None, model=None: scripted_llm)


def register(client, email=None, password="correct-horse-1"):
    email = email or f"{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/api/auth/register", json={"email": email, "password": password, "name": "T"})
    assert r.status_code == 201, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user"], email


def insert_repo(user_id, status="ready", name=None):
    with session_scope() as s:
        repo = Repository(user_id=uuid.UUID(user_id), url="https://github.com/o/x", owner="o",
                          name=name or f"x{uuid.uuid4().hex[:6]}", status=status)
        s.add(repo)
        s.flush()
        return str(repo.id)


# ------------------------------------------------------------------------------------ meta / CORS
def test_health_and_ready(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/health/ready").json() == {"status": "ready"}


def test_cors_allows_configured_origins_only(client):
    def preflight(origin):
        return client.options("/api/repos", headers={"Origin": origin, "Access-Control-Request-Method": "POST",
                                                     "Access-Control-Request-Headers": "authorization,content-type"})

    ok = preflight("https://app.example.com")
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == "https://app.example.com"
    preview = preflight("https://app-git-feature-me.vercel.app")
    assert preview.headers.get("access-control-allow-origin") == "https://app-git-feature-me.vercel.app"
    bad = preflight("https://evil.example.org")
    assert "access-control-allow-origin" not in bad.headers


# ------------------------------------------------------------------------------------ auth
def test_register_login_me_flow(client):
    headers, user, email = register(client)
    assert user["email"] == email and "password" not in str(user)
    assert client.get("/api/auth/me", headers=headers).json()["id"] == user["id"]

    ok = client.post("/api/auth/login", json={"email": email.upper(), "password": "correct-horse-1"})
    assert ok.status_code == 200 and ok.json()["token_type"] == "bearer"
    assert client.post("/api/auth/login", json={"email": email, "password": "wrong-password"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "whatever1"}).status_code == 401
    assert client.post("/api/auth/register", json={"email": email, "password": "correct-horse-1"}).status_code == 409


def test_validation_errors_never_echo_passwords(client):
    r = client.post("/api/auth/register", json={"email": "not-an-email", "password": "short"})
    assert r.status_code == 422 and r.json()["code"] == "validation_error"
    assert "short" not in r.text.replace("too short", "")
    r = client.post("/api/auth/register", json={"email": "a@b.co", "password": "x" * 80})
    assert r.status_code == 422


def test_protected_routes_require_valid_jwt(client):
    assert client.get("/api/repos").status_code == 401
    assert client.get("/api/repos", headers={"Authorization": "Bearer garbage"}).status_code == 401
    r = client.get("/api/auth/me")
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"

    from app.core.security import create_access_token
    expired = create_access_token(uuid.uuid4(), expires_minutes=-5)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    ghost = create_access_token(uuid.uuid4())  # valid signature, user does not exist
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {ghost}"}).status_code == 401


# ------------------------------------------------------------------------------------ URL validation
@pytest.mark.parametrize("url", [
    "http://evil.com/a/b", "https://github.com/onlyowner", "file:///etc/passwd", "https://github.com/a/b; rm -rf /",
    "--upload-pack=touch /tmp/pwn", "https://gitlab.com/a/b", "https://github.com/a/b/../../c", "ssh://git@github.com/a/b",
    "https://github.com/-bad/b", "https://github.com.evil.com/a/b",
])
def test_rejects_bad_repo_urls(client, url):
    headers, *_ = register(client)
    r = client.post("/api/repos", headers=headers, json={"url": url + " " * 0 if len(url) >= 10 else url.ljust(10, "x")})
    assert r.status_code == 422, (url, r.text)


def test_parse_github_url_accepts_valid_forms():
    r = parse_github_url("https://github.com/psf/requests")
    assert (r.owner, r.name, r.branch) == ("psf", "requests", None)
    assert parse_github_url("github.com/psf/requests.git/").clone_url == "https://github.com/psf/requests.git"
    assert parse_github_url("https://github.com/a/b/tree/feature/x").branch == "feature/x"
    assert parse_github_url("https://github.com/a/b", branch="dev").branch == "dev"
    with pytest.raises(ValidationFailure):
        parse_github_url("https://github.com/a/b", branch="--output=/etc/passwd")
    with pytest.raises(ValidationFailure):
        parse_github_url("https://github.com/a/b", branch="x/../y")


# ------------------------------------------------------------------------------------ authorization
def test_users_cannot_touch_each_others_repositories(client):
    ha, ua, _ = register(client)
    hb, ub, _ = register(client)
    rid = insert_repo(ua["id"])
    assert client.get(f"/api/repos/{rid}", headers=ha).status_code == 200
    for method, path, kw in [
        ("get", f"/api/repos/{rid}", {}), ("delete", f"/api/repos/{rid}", {}), ("post", f"/api/repos/{rid}/reindex", {}),
        ("get", f"/api/repos/{rid}/duplicates", {}), ("get", f"/api/repos/{rid}/history", {}),
        ("get", f"/api/repos/{rid}/conversations", {}),
        ("post", f"/api/repos/{rid}/query", {"json": {"question": "what is this?"}}),
    ]:
        r = getattr(client, method)(path, headers=hb, **kw)
        assert r.status_code == 404, (method, path, r.status_code)
    assert client.get("/api/repos", headers=hb).json() == []
    assert client.get(f"/api/repos/{uuid.uuid4()}", headers=ha).status_code == 404
    assert client.get("/api/repos/not-a-uuid", headers=ha).status_code == 422


def test_query_before_ready_is_rejected(client):
    h, u, _ = register(client)
    rid = insert_repo(u["id"], status="embedding")
    r = client.post(f"/api/repos/{rid}/query", headers=h, json={"question": "what does this do?"})
    assert r.status_code == 409 and r.json()["code"] == "repo_not_ready"
    r = client.delete(f"/api/repos/{rid}", headers=h)
    assert r.status_code == 409 and r.json()["code"] == "repo_busy"
    ready = insert_repo(u["id"], status="ready")  # ready but index row missing
    r = client.post(f"/api/repos/{ready}/query", headers=h, json={"question": "what does this do?"})
    assert r.status_code == 409 and "re-index" in r.json()["detail"]


def test_query_validation(client):
    h, u, _ = register(client)
    rid = insert_repo(u["id"])
    for body in ({"question": "hi"}, {"question": "x" * 2001}, {"question": "fine question", "mode": "hack"},
                 {"question": "fine question", "provider": "skynet"}, {"question": "fine question", "model": "a b;c"}):
        assert client.post(f"/api/repos/{rid}/query", headers=h, json=body).status_code == 422, body


# ------------------------------------------------------------------------------------ end to end (network)
def wait_ready(client, headers, rid, timeout=240):
    t0 = time.time()
    seen = []
    while time.time() - t0 < timeout:
        r = client.get(f"/api/repos/{rid}", headers=headers).json()
        if not seen or seen[-1] != r["status"]:
            seen.append(r["status"])
        if r["status"] in ("ready", "failed"):
            return r, seen
        time.sleep(0.5)
    raise AssertionError(f"timed out; statuses seen: {seen}")


@pytest.mark.network
def test_clone_failure_is_reported_on_the_repository(client):
    h, *_ = register(client)
    r = client.post("/api/repos", headers=h, json={"url": "https://github.com/octocat/this-repo-does-not-exist-zzz-404"})
    assert r.status_code == 202
    final, seen = wait_ready(client, h, r.json()["id"], timeout=90)
    assert final["status"] == "failed" and "not found or not public" in final["status_message"]


@pytest.mark.network
def test_full_workflow_with_real_github_repository(client, scripted_llm, tmp_path, settings):
    headers, user, _ = register(client)

    # --- submit & index (real git clone, real Tree-sitter, FAISS, DB persistence) --------------------------
    r = client.post("/api/repos", headers=headers, json={"url": "https://github.com/psf/requests"})
    assert r.status_code == 202, r.text
    rid = r.json()["id"]
    assert client.post("/api/repos", headers=headers, json={"url": "https://github.com/psf/requests"}).status_code == 409

    final, seen = wait_ready(client, headers, rid)
    assert final["status"] == "ready", final
    assert seen[0] in ("queued", "cloning") and "ready" == seen[-1]
    assert final["chunk_count"] > 100 and final["file_count"] > 20 and final["progress"] == 100
    assert final["languages"].get("python", 0) > 10 and len(final["commit_sha"]) == 40
    with session_scope() as s:
        row = s.get(RepoIndex, uuid.UUID(rid))
        assert row is not None and row.chunk_count == final["chunk_count"] and len(row.faiss_blob) > 100_000

    # --- grounded Q&A: citations must match the REAL upstream file contents ---------------------------------
    q = client.post(f"/api/repos/{rid}/query", headers=headers,
                    json={"question": "How does the Session class handle redirects?", "mode": "qa"})
    assert q.status_code == 200, q.text
    body = q.json()
    assert 2 <= len(body["sub_queries"]) <= 4 and body["citations"] and body["sources"]
    assert "does/not/exist.py" not in body["answer"] and body["removed_citations"] == 1
    assert body["llm_provider"] == "scripted" and set(body["timings_ms"]) == {"decompose", "retrieve", "dedupe", "generate"}

    check = tmp_path / "verify"
    sha = clone_repo(parse_github_url("https://github.com/psf/requests"), check, 120, 150)
    assert sha == final["commit_sha"], "upstream moved between clones; re-run"  # strict: never skip silently
    for src in body["sources"]:
        real = (check / src["path"]).read_text(encoding="utf-8", errors="replace").split("\n")
        assert src["code"] == "\n".join(real[src["start_line"] - 1:src["end_line"]]), src["path"]
    for c in body["citations"]:
        real = (check / c["path"]).read_text(encoding="utf-8", errors="replace").split("\n")
        assert 1 <= c["start_line"] <= c["end_line"] <= len(real)
    print(f"verified {len(body['sources'])} sources / {len(body['citations'])} citations against upstream files")
    assert all(c["start_line"] <= c["end_line"] for c in body["citations"])

    # --- conversation memory + history ----------------------------------------------------------------------
    cid = body["conversation_id"]
    scripted_llm.calls.clear()
    q2 = client.post(f"/api/repos/{rid}/query", headers=headers,
                     json={"question": "And what about cookies there?", "conversation_id": cid, "mode": "explain"})
    assert q2.status_code == 200 and q2.json()["conversation_id"] == cid
    assert [m["role"] for m in scripted_llm.calls[-1]["messages"]] == ["user", "assistant", "user"]
    hist = client.get(f"/api/repos/{rid}/history", headers=headers, params={"conversation_id": cid}).json()
    assert [h["mode"] for h in hist] == ["qa", "explain"]
    convs = client.get(f"/api/repos/{rid}/conversations", headers=headers).json()
    assert convs[0]["conversation_id"] == cid and convs[0]["messages"] == 2

    # --- other AI capabilities -----------------------------------------------------------------------------
    for mode in ("optimize", "duplicates"):
        r = client.post(f"/api/repos/{rid}/query", headers=headers,
                        json={"question": "headers and cookies handling", "mode": mode})
        assert r.status_code == 200 and r.json()["answer"], (mode, r.text)
    dups = client.get(f"/api/repos/{rid}/duplicates", headers=headers, params={"limit": 5})
    assert dups.status_code == 200 and {"groups", "scanned_chunks", "threshold"} <= set(dups.json())
    assert dups.json()["scanned_chunks"] > 50

    # --- re-index keeps working, then delete cascades ----------------------------------------------------------
    assert client.post(f"/api/repos/{rid}/reindex", headers=headers).status_code == 202
    again, _ = wait_ready(client, headers, rid)
    assert again["status"] == "ready"
    assert client.delete(f"/api/repos/{rid}", headers=headers).status_code == 204
    assert client.get(f"/api/repos/{rid}", headers=headers).status_code == 404
    with session_scope() as s:
        assert s.get(RepoIndex, uuid.UUID(rid)) is None
        assert s.query(QueryHistory).filter(QueryHistory.repo_id == uuid.UUID(rid)).count() == 0
