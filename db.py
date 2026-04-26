import sqlite3
import os

DB_PATH = "dog_behavior.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 결과를 dict처럼 사용 가능
    conn.execute("PRAGMA journal_mode=WAL")   # 동시 쓰기 성능 향상 (초당 10회 이상 로깅 무결성)
    conn.execute("PRAGMA foreign_keys = ON")  # FK CASCADE 활성화
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    NOT NULL UNIQUE,
            password      TEXT    NOT NULL,
            created_at    TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS videos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            filename        TEXT    NOT NULL,
            filepath        TEXT    NOT NULL,
            file_size       INTEGER NOT NULL,
            duration_sec    REAL,
            status          TEXT    NOT NULL DEFAULT 'pending',
            annotated_path  TEXT    DEFAULT '',  -- ← 추가
            uploaded_at     TEXT    NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS logs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id        INTEGER NOT NULL,
            timestamp_sec   REAL    NOT NULL,
            behavior_class  TEXT    NOT NULL,
            confidence      REAL    NOT NULL,
            nearby_objects  TEXT    DEFAULT '',  -- ← 추가 (JSON 문자열로 저장)
            created_at      TEXT    NOT NULL,
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
        );
    """)

    conn.commit()
    conn.close()
    print("[DB] 초기화 완료")

if __name__ == "__main__":
    init_db()