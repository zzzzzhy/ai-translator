import base64
import json
from .database import get_db
from typing import Dict, List, Optional
import base64
import json
from .database import get_db, DB_TYPE
from typing import Dict, List

def get_cached_translations(source_texts: List[str], source_lang: str, trans_lang: List[str]) -> Dict[str, Dict]:
    """批量获取缓存（自动Base64解码），根据目标语言匹配"""
    if not source_texts:
        return {}

    with get_db() as conn:
        if DB_TYPE == "mysql":
            placeholders = ", ".join(["%s"] * len(source_texts))
            query = f"SELECT source_text, translations_blob FROM translations_new WHERE source_text IN ({placeholders}) "
            params = [*source_texts]
            
            # 如果trans_lang不为空，添加trans_lang条件
            if trans_lang:
                query += " AND trans_lang = %s"
                # 对trans_lang进行排序，确保相同语言列表生成相同的JSON
                params.append(",".join(sorted(trans_lang)))
            
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
        else:
            placeholders = ", ".join(["?"] * len(source_texts))
            query = f"SELECT source_text, translations_blob FROM translations_new WHERE source_text IN ({placeholders}) "
            params = [*source_texts]
            
            # 如果trans_lang不为空，添加trans_lang条件
            if trans_lang:
                query += " AND trans_lang = ?"
                # 对trans_lang进行排序，确保相同语言列表生成相同的JSON
                params.append(",".join(sorted(trans_lang)))
            
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
    
    cached_translations = {}
    for row in rows:
        translations = json.loads(base64.b64decode(row["translations_blob"]).decode("utf-8"))
        source_text = row["source_text"]
        cached_translations[source_text] = translations
    return cached_translations
    
def save_translations_batch(items: List[Dict], translations: List[Dict], trans_lang: List[str]):
    """批量保存翻译结果（自动Base64编码），兼容MySQL和SQLite"""
    if not items:
        return

    data = []
    for item, trans in zip(items, translations):
        # 将整个翻译结果字典转为Base64
        blob = base64.b64encode(
            json.dumps(trans).replace("zh_tw", "zh-TW").encode('utf-8')
        ).decode('utf-8')
        # 将trans_lang列表转为JSON字符串，确保排序一致性
        trans_lang_json = ",".join(sorted(trans_lang))
        data.append((
            item["content"],
            item["lang"],
            trans_lang_json,
            blob
        ))

    with get_db('write') as conn:
        if DB_TYPE == "mysql":
            # MySQL使用ON DUPLICATE KEY UPDATE语法，基于唯一键更新
            query = """
                INSERT INTO translations_new 
                (source_text, source_lang, trans_lang, translations_blob) 
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    translations_blob = VALUES(translations_blob),
                    update_time = CURRENT_TIMESTAMP
            """
        else:
            # SQLite使用INSERT OR REPLACE语法
            query = """
                INSERT OR REPLACE INTO translations_new 
                (source_text, source_lang, trans_lang, translations_blob) 
                VALUES (?, ?, ?, ?)
            """
        
        if DB_TYPE == "mysql":
            cursor = conn.cursor()
            cursor.executemany(query, data)
            conn.commit()
            cursor.close()
        else:
            conn.executemany(query, data)
            conn.commit()