def test_strict_security_headers_and_auth_controls() -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert "unsafe-inline" not in res.headers["Content-Security-Policy"]
    assert "Strict-Transport-Security" in res.headers

    css_res = client.get("/styles.css")
    js_res = client.get("/app.js")
    assert css_res.status_code == 200
    assert js_res.status_code == 200

    unauth = client.post(
        "/api/wards",
        headers={"X-Operator-Token": "invalid-token"},
        json={"name": "Unauthorized Ward", "total": 10, "free": 5, "status": "Active"},
    )
    assert unauth.status_code == 401

    bad_path = client.post("/api/wards/../../etc/adjust", json={"delta": -1})
    assert bad_path.status_code in (404, 422)
