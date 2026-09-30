"""Seed the system: first training of the five regression models, demo user, first run in the DB.

Run:  python seed.py [--retrain]

Idempotent: the models are trained only if regression_models.pkl is missing (or
with --retrain), the demo account is created only if absent, and the first
training run is copied into model_runs only while that table is empty.
In single-service mode app.py calls `seed_database()` at startup, so an empty
database (a new Render Postgres, or a fresh SQLite file) gets the demo account.
"""

from __future__ import annotations

import argparse
import sys

import regression as reg
import security
import settings
from db_api.auth import create_user
from db_api.db import IntegrityError, connect
from db_api.explorer import viewer_usernames
from db_api.runs import TrainingRunIn, store_run

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo123"


def ensure_models(retrain: bool = False, log=print) -> dict:
    if retrain or not reg.MODELS_PATH.exists() or not reg.METRICS_PATH.exists():
        log("[seed] Huấn luyện 5 mô hình hồi quy lần đầu...")
        models, report = reg.train_all(log=log)
        report["trained_by"] = "seed"
        reg.save(models, report)
        return report
    return reg.load()[1]


def ensure_admins(conn, log=print) -> None:
    """Create the SQL-page accounts (SQL_VIEWER_USERS) with ADMIN_PASSWORD, or reset their
    password to it; without ADMIN_PASSWORD no such account exists and the page stays closed."""
    password = settings.get("ADMIN_PASSWORD")
    if not password:
        return
    for name in sorted(viewer_usernames()):
        row = conn.execute("SELECT id, password_hash FROM users WHERE lower(username) = lower(?)", (name,)).fetchone()
        if row is None:
            try:
                create_user(conn, name, password)
                log(f"[seed] Đã tạo tài khoản quản trị: {name} (mật khẩu = ADMIN_PASSWORD)")
            except IntegrityError:  # created concurrently by another worker
                pass
        elif not security.verify_password(password, row["password_hash"]):
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                         (security.hash_password(password), row["id"]))
            conn.commit()
            log(f"[seed] Đã cập nhật mật khẩu tài khoản quản trị {name} theo ADMIN_PASSWORD")


def seed_database(report: dict | None = None, log=print) -> None:
    """Create the demo and admin users and store the current evaluation table if the DB has none."""
    conn = connect()
    try:
        ensure_admins(conn, log)
        row = conn.execute("SELECT id FROM users WHERE lower(username) = lower(?)", (DEMO_USERNAME,)).fetchone()
        if row is None:
            try:
                user_id = create_user(conn, DEMO_USERNAME, DEMO_PASSWORD)
                log(f"[seed] Đã tạo tài khoản demo: {DEMO_USERNAME} / {DEMO_PASSWORD}")
            except IntegrityError:  # created concurrently by another worker
                user_id = conn.execute("SELECT id FROM users WHERE lower(username) = lower(?)", (DEMO_USERNAME,)).fetchone()[0]
        else:
            user_id = row[0]

        if conn.execute("SELECT COUNT(*) FROM training_runs").fetchone()[0] == 0:
            report = report or reg.load()[1]
            run_id = store_run(conn, user_id, TrainingRunIn(
                trained_at=report["trained_at"],
                target=report["task"]["target"],
                train_size=report["data"]["train_size"],
                test_size=report["data"]["test_size"],
                best_model=report["best_model"],
                total_seconds=report.get("total_seconds"),
                models=report["models"],
            ))
            log(f"[seed] Đã lưu bảng đánh giá 5 mô hình vào model_runs (lần train #{run_id})")
    finally:
        conn.close()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Khởi tạo dữ liệu: train lần đầu + tài khoản demo")
    parser.add_argument("--retrain", action="store_true", help="Train lại 5 mô hình dù đã có")
    args = parser.parse_args()
    report = ensure_models(args.retrain)
    seed_database(report)
    print("[seed] Xong.")


if __name__ == "__main__":
    main()
