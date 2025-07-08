import sqlite3
import base64
import json
import os
import asyncio
import aiomysql
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Dict, List
from time import sleep
from functools import wraps
from asyncio import Lock

DB_PATH = Path(os.getenv("DB_PATH", "translations.db"))
DB_TYPE = os.getenv("DB_TYPE", "sqlite")
DB_WRITE_CONFIG = {
    'host': os.getenv("DB_WRITE_HOST", "localhost"),
    'port': int(os.getenv("DB_WRITE_PORT", 3306)),
    'user': os.getenv("DB_USER", "root"),
    'password': os.getenv("DB_PASSWORD", ""),
    'db': os.getenv("DB_DATABASE", "translations"),
    'charset': 'utf8mb4',
    'autocommit': True,
}
DB_READ_CONFIG = {
    'host': os.getenv("DB_READ_HOST", "localhost"),
    'port': int(os.getenv("DB_READ_PORT", 3306)),
    'user': os.getenv("DB_USER", "root"),
    'password': os.getenv("DB_PASSWORD", ""),
    'db': os.getenv("DB_DATABASE", "translations"),
    'charset': 'utf8mb4',
    'autocommit': True,
}

# aiomysql 连接池
mysql_write_pool = None
mysql_read_pool = None

_pool_init_lock = Lock()


async def init_mysql_pools():
    global mysql_write_pool, mysql_read_pool
    if mysql_write_pool and mysql_read_pool:
        return
    async with _pool_init_lock:
        if not mysql_write_pool:
            mysql_write_pool = await aiomysql.create_pool(**DB_WRITE_CONFIG, maxsize=10)
        if not mysql_read_pool:
            mysql_read_pool = await aiomysql.create_pool(**DB_READ_CONFIG, maxsize=10)

# sqlite 依然用同步
@contextmanager
def get_db_sync(operation='read'):
    if DB_TYPE == 'mysql':
        raise RuntimeError('请使用异步 get_db')
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()

# aiomysql 异步上下文管理器
def retry_db_operation_async(max_retries=3, delay=1):
    def decorator(f):
        @wraps(f)
        async def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return await f(*args, **kwargs)
                except (aiomysql.Error, Exception) as e:
                    retries += 1
                    if retries == max_retries:
                        raise
                    await asyncio.sleep(delay)
        return wrapper
    return decorator

@asynccontextmanager
async def get_mysql_conn(operation='read'):
    await init_mysql_pools()
    pool = mysql_write_pool if operation == 'write' else mysql_read_pool
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            try:
                yield conn, cursor
            except Exception:
                await conn.rollback()
                raise

@contextmanager
def get_sqlite_conn(operation='read'):
    with get_db_sync(operation) as conn:
        yield conn, conn.cursor()

# get_db 调用中使用
@asynccontextmanager
async def get_db(operation='read'):
    if DB_TYPE == 'mysql':
        async with get_mysql_conn(operation) as (conn, cursor):
            yield conn, cursor
    else:
        with get_sqlite_conn(operation) as (conn, cursor):
            yield conn, cursor

async def init_db():
    """
    初始化数据库（使用Base64存储）
    """
    if DB_TYPE == "mysql":
        await init_mysql_pools()
        async with mysql_write_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
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
                await conn.commit()
    else:
        with get_db_sync('write') as conn:
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
            conn.execute("CREATE INDEX IF NOT EXISTS idx_source_text ON translations_new(source_text)")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uk_source_text_lang ON translations_new(source_text, source_lang, trans_lang)")
            conn.commit()
