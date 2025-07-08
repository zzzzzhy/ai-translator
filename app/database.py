import sqlite3
import base64
import json
import os
import pymysql
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List
from dbutils.persistent_db  import PersistentDB
from time import sleep
from functools import wraps

DB_PATH = Path(os.getenv("DB_PATH", "translations.db"))
DB_TYPE = os.getenv("DB_TYPE", "sqlite")
DB_WRITE_CONFIG = {
    'host': os.getenv("DB_WRITE_HOST", "localhost"),
    'port': int(os.getenv("DB_WRITE_PORT", 3306)),
    'user': os.getenv("DB_USER", "root"),
    'password': os.getenv("DB_PASSWORD", ""),
    'database': os.getenv("DB_DATABASE", "translations"),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
}
DB_READ_CONFIG = {
    'host': os.getenv("DB_READ_HOST", "localhost"),
    'port': int(os.getenv("DB_READ_PORT", 3306)),
    'user': os.getenv("DB_USER", "root"),
    'password': os.getenv("DB_PASSWORD", ""),
    'database': os.getenv("DB_DATABASE", "translations"),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
}

# 创建MySQL连接池
if DB_TYPE == 'mysql':
    write_pool = PersistentDB(
        creator=pymysql,
        maxusage=100,
        autocommit=True,
        **DB_WRITE_CONFIG
    )
    read_pool = PersistentDB(
        creator=pymysql,
        maxusage=100,
        autocommit=True,
        **DB_READ_CONFIG
    )

def retry_db_operation(max_retries=3, delay=1):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return f(*args, **kwargs)
                except (pymysql.Error, sqlite3.Error) as e:
                    retries += 1
                    if retries == max_retries:
                        raise
                    sleep(delay)
        return wrapper
    return decorator
@contextmanager
@retry_db_operation()
def get_db(operation='read'):
    """获取数据库连接(支持读写分离)
    
    Args:
        operation: 'read' or 'write'
    """
    if DB_TYPE == 'mysql':
        if operation == 'write':
            conn = write_pool.connection()
        else:
            conn = read_pool.connection()
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

    try:
        yield conn
    except Exception as e:
        conn.rollback()
        raise
    finally:
        if DB_TYPE == 'mysql':
            conn.close()  # 归还连接到连接池
        else:
            conn.close()  # SQLite直接关闭连接

def init_db():
    """初始化数据库（使用Base64存储）"""
    with get_db('write') as conn:
        if DB_TYPE == "mysql":
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS translations_new (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    source_text VARCHAR(255) NOT NULL,
                    source_lang VARCHAR(10) NOT NULL,
                    trans_lang TEXT NOT NULL,
                    translations_blob TEXT NOT NULL,
                    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_source_text (source_text),
                    UNIQUE KEY uk_source_text_lang (source_text, source_lang, trans_lang(100))
                );
            """)
            conn.commit()
            cursor.close()
        else:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS translations_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_text TEXT NOT NULL,
                    source_lang TEXT NOT NULL,
                    trans_lang TEXT NOT NULL,
                    translations_blob TEXT NOT NULL,
                    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    update_time DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # SQLite创建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_source_text ON translations_new(source_text)")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uk_source_text_lang ON translations_new(source_text, source_lang, trans_lang)")
            conn.commit()
