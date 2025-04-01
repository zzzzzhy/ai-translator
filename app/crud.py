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
                f"WHERE source_text IN ({placeholders}) AND source_lang = %s"
            )
            cursor = conn.cursor()
            cursor.execute(query, (*source_texts, source_lang))
            rows = cursor.fetchall()
            cursor.close()
        else:
            placeholders = ", ".join(["?"] * len(source_texts))
            query = (
                f"SELECT source_text, translations_blob FROM translations "
                f"WHERE source_text IN ({placeholders}) AND source_lang = ?"
            )
            cursor = conn.execute(query, (*source_texts, source_lang))
            rows = cursor.fetchall()

    cached_translations = {}
    for row in rows:
        if DB_TYPE == "mysql":
            source_text, translations_blob = row
            translations = json.loads(base64.b64decode(translations_blob).decode("utf-8"))
        else:
            translations = json.loads(base64.b64decode(row["translations_blob"]).decode("utf-8"))
            source_text = row["source_text"]
        cached_translations[source_text] = translations

    return cached_translations
    
def save_translations_batch(translations: Dict[str, Dict], source_lang: str):
    """批量保存翻译（自动Base64编码）"""
    with get_db() as conn:
        if DB_TYPE == "mysql":
            cursor = conn.cursor()
            for source_text, translation in translations.items():
                translations_blob = base64.b64encode(json.dumps(translation).encode("utf-8")).decode("utf-8")
                cursor.execute(
                    "REPLACE INTO translations (source_text, source_lang, translations_blob) VALUES (%s, %s, %s)",
                    (source_text, source_lang, translations_blob)
                )
            conn.commit()
            cursor.close()
        else:
            for source_text, translation in translations.items():
                translations_blob = base64.b64encode(json.dumps(translation).encode("utf-8")).decode("utf-8")
                conn.execute(
                    "REPLACE INTO translations (source_text, source_lang, translations_blob) VALUES (?, ?, ?)",
                    (source_text, source_lang, translations_blob)
                )
            conn.commit()