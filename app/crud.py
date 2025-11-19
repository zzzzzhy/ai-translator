import base64
import json
from .database import get_db, DB_TYPE, retry_db_operation_async
from typing import Dict, List

@retry_db_operation_async()
async def get_cached_translations(source_texts: List[str], source_lang: str, trans_lang: List[str]) -> Dict[str, Dict]:
    """批量获取缓存（自动Base64解码），根据目标语言匹配"""
    if not source_texts:
        return {}

    if DB_TYPE == "mysql":
        placeholders = ", ".join(["%s"] * len(source_texts))
        query = f"SELECT source_text, translations_blob FROM translations_new WHERE source_text IN ({placeholders}) "
        params = [*source_texts]
        if trans_lang:
            query += " AND trans_lang = %s"
            params.append(",".join(sorted(trans_lang)))
        async with get_db() as (conn, cursor):
            await cursor.execute(query, params)
            rows = await cursor.fetchall()
    else:
        placeholders = ", ".join(["?"] * len(source_texts))
        query = f"SELECT source_text, translations_blob FROM translations_new WHERE source_text IN ({placeholders}) "
        params = [*source_texts]
        if trans_lang:
            query += " AND trans_lang = ?"
            params.append(",".join(sorted(trans_lang)))
        async with get_db('read') as (conn, cursor):
            cursor.execute(query, params)
            rows = cursor.fetchall()

    cached_translations = {}
    for row in rows:
        translations = json.loads(base64.b64decode(row["translations_blob"]).decode("utf-8"))
        source_text = row["source_text"]
        cached_translations[source_text] = translations
    return cached_translations
    
async def save_translations_batch(items: List[Dict], translations: List[Dict], trans_lang: List[str]):
    """批量保存翻译结果（自动Base64编码），兼容MySQL和SQLite"""
    if not items:
        return

    data = []
    for item, trans in zip(items, translations):
        blob = base64.b64encode(
            json.dumps(trans).replace("zh_tw", "zh-TW").encode('utf-8')
        ).decode('utf-8')
        trans_lang_json = ",".join(sorted(trans_lang))
        data.append((
            item["content"],
            item["lang"],
            trans_lang_json,
            blob
        ))

    if DB_TYPE == "mysql":
        query = """
            INSERT INTO translations_new 
            (source_text, source_lang, trans_lang, translations_blob) 
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                translations_blob = VALUES(translations_blob),
                update_time = CURRENT_TIMESTAMP
        """
        async with get_db('write') as (conn, cursor):
            await cursor.executemany(query, data)
            await conn.commit()
    else:
        query = """
            INSERT OR REPLACE INTO translations_new 
            (source_text, source_lang, trans_lang, translations_blob) 
            VALUES (?, ?, ?, ?)
        """
        async with get_db('write') as (conn, cursor):
            cursor.executemany(query, data)
            conn.commit()