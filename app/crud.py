import base64
import json
from .database import get_db
from typing import Dict, List, Optional
import base64
import json
from .database import get_db, DB_TYPE
from typing import Dict, List

def get_cached_translations(source_texts: List[str], source_lang: str) -> Dict[str, Dict]:
    """批量获取缓存（自动Base64解码）"""
    if not source_texts:
        return {}

    with get_db() as conn:
        if DB_TYPE == "mysql":
            placeholders = ", ".join(["%s"] * len(source_texts))
            query = (
                f"SELECT source_text, translations_blob FROM translations "
                f"WHERE source_text IN ({placeholders})"
            )
            cursor = conn.cursor()
            cursor.execute(query, *source_texts)
            rows = cursor.fetchall()
            cursor.close()
        else:
            placeholders = ", ".join(["?"] * len(source_texts))
            query = (
                f"SELECT source_text, translations_blob FROM translations "
                f"WHERE source_text IN ({placeholders}) "
            )
            cursor = conn.execute(query, *source_texts)
            rows = cursor.fetchall()
    cached_translations = {}
    for row in rows:
        translations = json.loads(base64.b64decode(row["translations_blob"]).decode("utf-8"))
        source_text = row["source_text"]
        cached_translations[source_text] = translations
    return cached_translations
    
def save_translations_batch(items: List[Dict], translations: List[Dict]):
    """批量保存翻译结果（自动Base64编码），兼容MySQL和SQLite"""
    if not items:
        return

    data = []
    for item, trans in zip(items, translations):
        # 将整个翻译结果字典转为Base64
        blob = base64.b64encode(
            json.dumps(trans).replace("zh_tw", "zh-TW").encode('utf-8')
        ).decode('utf-8')
        data.append((
            item["content"],
            item["lang"],
            blob
        ))

    with get_db('write') as conn:
        # 检测是否是MySQL（通过检查是否有cursor()方法）
        # is_mysql = hasattr(conn, 'cursor')
        
        if DB_TYPE == "mysql":
            # MySQL使用ON DUPLICATE KEY UPDATE语法
            query = """
                INSERT INTO translations 
                (source_text, source_lang, translations_blob) 
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE translations_blob = VALUES(translations_blob)
            """
        else:
            # SQLite使用INSERT OR REPLACE语法
            query = """
                INSERT OR REPLACE INTO translations 
                (source_text, source_lang, translations_blob) 
                VALUES (?, ?, ?)
            """
        
        if DB_TYPE == "mysql":
            cursor = conn.cursor()
            cursor.executemany(query, data)
            conn.commit()
            cursor.close()
        else:
            conn.executemany(query, data)
            conn.commit()