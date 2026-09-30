"""Read-only SQL explorer (/db/sql/*): access control, hidden columns, and no way to write."""

import pytest

from conftest import ADMIN_PASSWORD, SETOSA


def _login(client, username, password):
    res = client.post("/db/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def admin(client):
    return _login(client, "admin", ADMIN_PASSWORD)


def _count(client, admin, table):
    res = client.post("/db/sql/query", headers=admin, json={"sql": f"SELECT COUNT(*) AS n FROM {table}"})
    return res.json()["rows"][0][0]


def test_only_the_admin_account_may_read(client, user):
    assert client.get("/db/sql/tables").status_code == 401
    assert client.get("/db/sql/tables", headers=user["headers"]).status_code == 403
    # The public demo account (password shown on the login page) is not an admin.
    demo = _login(client, "demo", "demo123")
    assert client.get("/db/sql/tables", headers=demo).status_code == 403
    assert client.post("/db/sql/query", headers=demo, json={"sql": "SELECT 1"}).status_code == 403


def test_admin_name_cannot_be_registered(client):
    for name in ("admin", "ADMIN"):
        res = client.post("/db/auth/register", json={"username": name, "password": "secret123"})
        assert res.status_code == 409


def test_tables_show_username_not_user_id(client, admin, user):
    client.post("/db/predictions", headers=user["headers"], json={"items": [
        {"task": "classification", "model": "svm", "input": SETOSA, "predicted_label": "setosa"}]})
    tables = {t["name"]: t for t in client.get("/db/sql/tables", headers=admin).json()["tables"]}
    assert {"users", "predictions", "training_runs", "model_runs"} <= set(tables)
    assert tables["predictions"]["columns"][:2] == ["id", "username"]
    assert "user_id" not in tables["predictions"]["columns"]
    assert "password_hash" not in tables["users"]["columns"]

    rows = client.get("/db/sql/tables/predictions?limit=5", headers=admin).json()
    assert "user_id" not in rows["columns"]
    assert rows["rows"][0][1] == user["username"]
    users = client.get("/db/sql/tables/users", headers=admin).json()
    assert "password_hash" not in users["columns"]
    assert client.get("/db/sql/tables/not_a_table", headers=admin).status_code == 404


def test_password_hashes_never_leave_the_server(client, admin):
    res = client.post("/db/sql/query", headers=admin, json={"sql": "SELECT password_hash AS x FROM users"})
    assert res.status_code == 400
    res = client.post("/db/sql/query", headers=admin, json={"sql": "SELECT * FROM users"})
    assert res.status_code == 200, res.text
    assert all("$2b$" not in str(v) for row in res.json()["rows"] for v in row)


@pytest.mark.parametrize("sql", [
    "DELETE FROM predictions",
    "UPDATE users SET username = 'x'",
    "DROP TABLE predictions",
    "SELECT 1; DELETE FROM predictions",
    "SELECT 1; COMMIT; DROP TABLE predictions",
    "WITH gone AS (DELETE FROM predictions RETURNING id) SELECT * FROM gone",
])
def test_writes_are_rejected(client, admin, sql):
    before = _count(client, admin, "predictions")
    res = client.post("/db/sql/query", headers=admin, json={"sql": sql})
    assert res.status_code == 400, res.text
    assert _count(client, admin, "predictions") == before
