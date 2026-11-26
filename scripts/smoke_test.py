#!/usr/bin/env python3
"""End-to-end smoke test for a running deployment (local or Render). Standard library only.

Walks the same path the React app does: CORS preflight from the Vercel origin -> register -> login -> add GitHub
repo -> poll indexing status -> ask a question -> verify grounded file/line citations -> history -> cleanup.

  python scripts/smoke_test.py --api https://YOUR-SERVICE.onrender.com --origin https://YOUR-APP.vercel.app
Exit code 0 = every check passed.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid


def call(method, url, body=None, token=None, origin=None, timeout=180):
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if origin:
        headers["Origin"] = origin
    req = urllib.request.Request(url, method=method, headers=headers,
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, dict(r.headers), (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, dict(e.headers), json.loads(raw)
        except ValueError:
            return e.code, dict(e.headers), raw.decode(errors="replace")


FAILS = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -> {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)
    return cond


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True, help="Backend base URL, no trailing slash, no /api")
    ap.add_argument("--origin", default="", help="Frontend origin (your Vercel URL) to test CORS with")
    ap.add_argument("--repo", default="https://github.com/psf/requests")
    ap.add_argument("--question", default="How does the Session class handle redirects?")
    ap.add_argument("--timeout", type=int, default=900, help="Max seconds to wait for indexing")
    ap.add_argument("--keep", action="store_true", help="Do not delete the repository afterwards")
    a = ap.parse_args()
    base = a.api.rstrip("/") + "/api"

    print("1. Backend reachable (free-tier hosts may need ~1 min to wake)")
    t0 = time.time()
    s, _, body = call("GET", f"{base}/health", timeout=120)
    check("GET /api/health -> ok", s == 200 and body == {"status": "ok"}, f"{s} {body}")
    s, _, body = call("GET", f"{base}/health/ready")
    check("database reachable (Neon)", s == 200 and body.get("status") == "ready", f"{s} {body}")

    if a.origin:
        print("2. CORS from the frontend origin")
        req = urllib.request.Request(f"{base}/repos", method="OPTIONS", headers={
            "Origin": a.origin, "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                allow = r.headers.get("access-control-allow-origin")
        except urllib.error.HTTPError as e:
            allow = e.headers.get("access-control-allow-origin")
        check("preflight allows the frontend origin", allow == a.origin, f"allow-origin={allow!r}")

    print("3. Authentication")
    email, pw = f"smoke-{uuid.uuid4().hex[:8]}@example.com", "smoke-Test-pw-123"
    s, h, body = call("POST", f"{base}/auth/register", {"email": email, "password": pw}, origin=a.origin or None)
    check("register -> 201 + token", s == 201 and "access_token" in (body or {}), f"{s} {body}")
    if a.origin:
        check("register response carries CORS header", h.get("access-control-allow-origin") == a.origin, str(h))
    s, _, body = call("POST", f"{base}/auth/login", {"email": email, "password": pw})
    check("login -> 200 + token", s == 200 and "access_token" in (body or {}), f"{s} {body}")
    token = (body or {}).get("access_token")
    if not token:
        return finish()
    s, _, _ = call("GET", f"{base}/repos")
    check("protected route without token -> 401", s == 401)
    s, _, body = call("GET", f"{base}/auth/me", token=token)
    check("GET /auth/me", s == 200 and body.get("email") == email, f"{s} {body}")

    print(f"4. Index {a.repo}")
    s, _, repo = call("POST", f"{base}/repos", {"url": a.repo}, token=token)
    if not check("POST /repos -> 202", s == 202, f"{s} {repo}"):
        return finish()
    rid, seen, final = repo["id"], [], None
    start = time.time()
    while time.time() - start < a.timeout:
        _, _, r = call("GET", f"{base}/repos/{rid}", token=token)
        if not seen or seen[-1] != r["status"]:
            seen.append(r["status"])
            print(f"     status={r['status']} progress={r['progress']} {r.get('status_message') or ''}")
        if r["status"] in ("ready", "failed"):
            final = r
            break
        time.sleep(3)
    check("indexing reaches 'ready'", bool(final) and final["status"] == "ready", f"statuses={seen} final={final}")
    if not final or final["status"] != "ready":
        return finish()
    check("chunks + files + languages recorded", final["chunk_count"] > 0 and final["file_count"] > 0 and bool(final["languages"]))

    print("5. Grounded query")
    s, _, q = call("POST", f"{base}/repos/{rid}/query", {"question": a.question, "mode": "qa"}, token=token)
    if not check("POST /query -> 200", s == 200, f"{s} {q}"):
        return finish()
    check("2-4 sub-queries", 2 <= len(q["sub_queries"]) <= 4, str(q["sub_queries"]))
    check("answer is non-empty", len(q["answer"].strip()) > 20)
    check("has sources with code", bool(q["sources"]) and all(src["code"] for src in q["sources"]))
    cites = q["citations"]
    check("answer carries file+line citations", bool(cites), "the LLM produced no valid citations")
    ok = all(any(c["path"] == s_["path"] and s_["start_line"] <= c["start_line"] <= c["end_line"] <= s_["end_line"]
                 for s_ in q["sources"]) for c in cites)
    check("every citation lies inside a retrieved source (no invented lines)", ok)
    for c in cites[:5]:
        print(f"     cited {c['path']}:{c['start_line']}-{c['end_line']}  ({c['kind']} {c['name']})")
    check("LLM provider/model reported", bool(q.get("llm_provider") and q.get("llm_model")), f"{q.get('llm_provider')}/{q.get('llm_model')}")

    print("6. Conversation history")
    s, _, q2 = call("POST", f"{base}/repos/{rid}/query", {"question": "Summarize that in one sentence.", "mode": "explain",
                                                          "conversation_id": q["conversation_id"]}, token=token)
    check("follow-up in same conversation", s == 200 and q2["conversation_id"] == q["conversation_id"], f"{s}")
    s, _, hist = call("GET", f"{base}/repos/{rid}/history?conversation_id={q['conversation_id']}", token=token)
    check("history lists both turns", s == 200 and len(hist) == 2, f"{s} {len(hist) if isinstance(hist, list) else hist}")

    if not a.keep:
        print("7. Cleanup")
        s, _, _ = call("DELETE", f"{base}/repos/{rid}", token=token)
        check("DELETE repo -> 204", s == 204, str(s))
    return finish(time.time() - t0)


def finish(elapsed=None):
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}): " + "; ".join(FAILS))
        sys.exit(1)
    print("ALL CHECKS PASSED" + (f" in {elapsed:.0f}s" if elapsed else ""))
    sys.exit(0)


if __name__ == "__main__":
    main()
