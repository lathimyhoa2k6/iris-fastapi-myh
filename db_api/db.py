"""Database access for the database API, with numbered SQL migrations.

Backend: SQLite (DB_PATH) by default; PostgreSQL when DATABASE_URL is set (Render
Postgres in production). The PostgreSQL connection is wrapped so the routers keep
the sqlite3 API: '?' placeholders, rows readable by index or column name,
cursor.lastrowid after an INSERT.

Each file in migrations/ (PostgreSQL: migrations/postgres/) runs once, in name
order, and is recorded in the schema_migrations table. Schema changes go into a
new numbered file for both backends; existing files are never edited, so existing
data is never dropped.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import settings

try:
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    from psycopg_pool import ConnectionPool
except ImportError:  # SQLite-only install
    psycopg = None

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
PG_MIGRATIONS_DIR = MIGRATIONS_DIR / "postgres"
_migrated: set[str] = set()
_pools: dict[str, "ConnectionPool"] = {}
_lock = threading.Lock()

# Catch this instead of sqlite3.IntegrityError so both backends are handled.
IntegrityError: tuple[type[Exception], ...] = (sqlite3.IntegrityError,) + (
    (psycopg.IntegrityError,) if psycopg else ()
)


UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime(UTC_FORMAT)


def local_tz() -> timezone:
    """Timezone used for date filters and Excel timestamps (Vietnam, UTC+7, by default)."""
    return timezone(timedelta(hours=float(settings.get("APP_TZ_OFFSET_HOURS", "7"))))


def date_bounds(date_from: date | None, date_to: date | None) -> tuple[str | None, str | None]:
    """Local calendar days -> UTC ISO bounds [start, end) for created_at comparisons."""

    def utc(d: date) -> str:
        return datetime.combine(d, time.min, local_tz()).astimezone(timezone.utc).strftime(UTC_FORMAT)

    return (utc(date_from) if date_from else None, utc(date_to + timedelta(days=1)) if date_to else None)


def describe() -> str:
    """Backend shown by /db/health, without host or credentials."""
    url = settings.database_url()
    if url:
        return f"postgresql/{conninfo_to_dict(url).get('dbname', '')}"
    return settings.db_path().name


# ----------------------------------------------------------------- SQLite


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Apply pending migrations and return the versions that were applied."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    applied = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = path.stem
        if version in done:
            continue
        conn.executescript(path.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", (version, utc_now()))
        conn.commit()
        applied.append(version)
    return applied


def _connect_sqlite() -> sqlite3.Connection:
    path = settings.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    key = str(path.resolve())
    if key not in _migrated:
        with _lock:
            if key not in _migrated:
                applied = migrate(conn)
                if applied:
                    print(f"[db] Applied migrations {applied} to {path}")
                _migrated.add(key)
    return conn


# ------------------------------------------------------------- PostgreSQL


class PgRow(dict):
    """Row readable like sqlite3.Row: row[0] by position, row["col"] by name, dict(row)."""

    def __init__(self, columns: list[str], values) -> None:
        super().__init__(zip(columns, values))
        self._values = tuple(values)

    def __getitem__(self, key):
        return self._values[key] if isinstance(key, int) else super().__getitem__(key)


def _row_factory(cursor):
    columns = [c.name for c in cursor.description] if cursor.description else []
    return lambda values: PgRow(columns, values)


class PgCursor:
    """psycopg cursor plus the lastrowid attribute of sqlite3 cursors."""

    def __init__(self, cursor, lastrowid: int | None) -> None:
        self._cursor = cursor
        self.lastrowid = lastrowid

    def __getattr__(self, name):
        return getattr(self._cursor, name)

    def __iter__(self):
        return iter(self._cursor)


class PgConnection:
    """The subset of sqlite3.Connection the routers use, on a pooled psycopg connection."""

    def __init__(self, pool: "ConnectionPool", conn) -> None:
        self._pool = pool
        self.raw = conn

    def execute(self, sql: str, params=()) -> PgCursor:
        sql = sql.replace("%", "%%").replace("?", "%s")
        returning_id = sql.lstrip().upper().startswith("INSERT") and "RETURNING" not in sql.upper()
        if returning_id:
            sql += " RETURNING id"
        try:
            cur = self.raw.execute(sql, params)
        except psycopg.Error:
            # A failed statement aborts the transaction; reset it so the connection stays usable.
            self.raw.rollback()
            raise
        return PgCursor(cur, cur.fetchone()[0] if returning_id else None)

    def commit(self) -> None:
        self.raw.commit()

    def close(self) -> None:
        try:
            self.raw.rollback()  # end read-only transactions before returning to the pool
        except psycopg.Error:
            pass
        self._pool.putconn(self.raw)


def _migrate_postgres(conn) -> list[str]:
    """Apply pending PostgreSQL migrations in one transaction, serialised by an advisory lock."""
    conn.execute("SELECT pg_advisory_xact_lock(7294001)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    applied = []
    for path in sorted(PG_MIGRATIONS_DIR.glob("*.sql")):
        version = path.stem
        if version in done:
            continue
        conn.execute(path.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (%s, %s)", (version, utc_now()))
        applied.append(version)
    conn.commit()
    return applied


def _pool(url: str) -> "ConnectionPool":
    if psycopg is None:
        raise RuntimeError("DATABASE_URL is set but psycopg is not installed (pip install -r requirements.txt)")
    with _lock:
        if url not in _pools:
            _pools[url] = ConnectionPool(
                url,
                min_size=1,
                max_size=int(settings.get("DB_POOL_SIZE", "5")),
                kwargs={"row_factory": _row_factory},
                check=ConnectionPool.check_connection,  # drop connections the server closed while idle
                open=True,
            )
        return _pools[url]


def _connect_postgres(url: str) -> PgConnection:
    pool = _pool(url)
    conn = PgConnection(pool, pool.getconn())
    if url not in _migrated:
        with _lock:
            if url not in _migrated:
                try:
                    applied = _migrate_postgres(conn.raw)
                except Exception:
                    conn.close()
                    raise
                if applied:
                    print(f"[db] Applied migrations {applied} to {describe()}")
                _migrated.add(url)
    return conn


# ----------------------------------------------------------------- public


def connect():
    """Open a connection (PostgreSQL if DATABASE_URL is set, else the SQLite file at DB_PATH),
    creating the schema on first use."""
    url = settings.database_url()
    return _connect_postgres(url) if url else _connect_sqlite()


def get_conn():
    """FastAPI dependency: one connection per request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
