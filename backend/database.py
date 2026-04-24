import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "interactions.db"


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path or str(DEFAULT_DB_PATH))
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: str | None = None) -> None:
    with get_connection(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hcp_name TEXT NOT NULL,
                interaction_type TEXT,
                date TEXT,
                time TEXT,
                attendees TEXT,
                topics TEXT,
                materials TEXT,
                sentiment TEXT,
                outcomes TEXT,
                follow_up_actions TEXT
            )
            """
        )
        connection.commit()


def row_to_interaction(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] or "" for key in row.keys()}


def list_interactions(db_path: str | None = None) -> list[dict[str, Any]]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, hcp_name, interaction_type, date, time, attendees, topics, materials,
                   sentiment, outcomes, follow_up_actions
            FROM interactions
            ORDER BY id DESC
            """
        ).fetchall()
    return [row_to_interaction(row) for row in rows if row_to_interaction(row) is not None]


def get_interaction(interaction_id: int, db_path: str | None = None) -> dict[str, Any] | None:
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT id, hcp_name, interaction_type, date, time, attendees, topics, materials,
                   sentiment, outcomes, follow_up_actions
            FROM interactions
            WHERE id = ?
            """,
            (interaction_id,),
        ).fetchone()
    return row_to_interaction(row)


def insert_interaction(entry: dict[str, Any], db_path: str | None = None) -> dict[str, Any]:
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO interactions (
                hcp_name, interaction_type, date, time, attendees, topics, materials,
                sentiment, outcomes, follow_up_actions
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.get("hcp_name", ""),
                entry.get("interaction_type", ""),
                entry.get("date", ""),
                entry.get("time", ""),
                entry.get("attendees", ""),
                entry.get("topics", ""),
                entry.get("materials", ""),
                entry.get("sentiment", ""),
                entry.get("outcomes", ""),
                entry.get("follow_up_actions", ""),
            ),
        )
        connection.commit()
        interaction_id = cursor.lastrowid
    return get_interaction(int(interaction_id), db_path) or {}


def update_interaction(
    interaction_id: int,
    entry: dict[str, Any],
    db_path: str | None = None,
) -> dict[str, Any]:
    with get_connection(db_path) as connection:
        connection.execute(
            """
            UPDATE interactions
            SET hcp_name = ?, interaction_type = ?, date = ?, time = ?, attendees = ?, topics = ?,
                materials = ?, sentiment = ?, outcomes = ?, follow_up_actions = ?
            WHERE id = ?
            """,
            (
                entry.get("hcp_name", ""),
                entry.get("interaction_type", ""),
                entry.get("date", ""),
                entry.get("time", ""),
                entry.get("attendees", ""),
                entry.get("topics", ""),
                entry.get("materials", ""),
                entry.get("sentiment", ""),
                entry.get("outcomes", ""),
                entry.get("follow_up_actions", ""),
                interaction_id,
            ),
        )
        connection.commit()
    return get_interaction(interaction_id, db_path) or {}
