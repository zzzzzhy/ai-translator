import sqlite3
import base64
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List

DB_PATH = Path("translations.db")

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """初始化数据库（使用Base64存储）"""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS translations (
                source_text TEXT PRIMARY KEY,
                source_lang TEXT NOT NULL,
                translations_blob TEXT NOT NULL,  -- Base64编码的JSON
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_translation_search 
            ON translations(source_text, source_lang)
        """)