import sqlite3
import base64
import json
import os
import pymysql
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List

DB_PATH = Path(os.getenv("DB_PATH", "translations.db"))  # 通过环境变量选择数据库路径，默认为 translations.db
DB_TYPE = os.getenv("DB_TYPE", "sqlite")  # 通过环境变量选择数据库类型，默认为sqlite

@contextmanager
def get_db():
    if DB_TYPE == "mysql":
        conn = pymysql.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "translations")
        )
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """初始化数据库（使用Base64存储）"""
    with get_db() as conn:
        if DB_TYPE == "mysql":
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS translations (
                    source_text VARCHAR(255) PRIMARY KEY,
                    source_lang VARCHAR(10) NOT NULL,
                    translations_blob TEXT NOT NULL  -- Base64编码的JSON
                )
            """)
            conn.commit()
            cursor.close()
        else:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS translations (
                    source_text TEXT PRIMARY KEY,
                    source_lang TEXT NOT NULL,
                    translations_blob TEXT NOT NULL  -- Base64编码的JSON
                )
            """)