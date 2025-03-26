import base64
import json
from .database import get_db
from typing import Dict, List, Optional

def get_cached_translations(source_texts: List[str], source_lang: str) -> Dict[str, Dict]:
    """批量获取缓存（自动Base64解码）"""
    if not source_texts:
        return {}

    placeholders = ", ".join(["?"] * len(source_texts))
    with get_db() as conn:
        cursor = conn.execute(
            f"SELECT source_text, translations_blob FROM translations "
            f"WHERE source_text IN ({placeholders}) AND source_lang = ?",
            (*source_texts, source_lang)
        )
        return {
            row["source_text"]: json.loads(base64.b64decode(row["translations_blob"]).decode('utf-8'))
            for row in cursor
        }

def save_translations_batch(items: List[Dict], translations: List[Dict]):
    """批量保存翻译结果（自动Base64编码）"""
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

    with get_db() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO translations "
            "(source_text, source_lang, translations_blob) "
            "VALUES (?, ?, ?)",
            data
        )
        conn.commit()