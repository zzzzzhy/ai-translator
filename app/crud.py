from .database import get_db
from typing import List, Dict

def get_cached_translations(items: List[Dict], target_lang: str) -> Dict[str, str]:
    """批量查询缓存"""
    if not items:
        return {}
    
    placeholders = ", ".join(["?"] * len(items))
    source_texts = [item["content"] for item in items]
    source_lang = items[0]["lang"]
    
    with get_db() as conn:
        cursor = conn.execute(
            f"""
            SELECT source_text, translated_text 
            FROM translations 
            WHERE source_text IN ({placeholders})
            AND source_lang = ?
            AND target_lang = ?
            """,
            (*source_texts, source_lang, target_lang))
        return {row["source_text"]: row["translated_text"] for row in cursor}

def bulk_save_translations(items: List[Dict], translations: List[str], target_lang: str):
    """批量保存翻译结果"""
    if not items:
        return
    
    data = [
        (item["content"], items[0]["lang"], target_lang, translations[i])
        for i, item in enumerate(items)
    ]
    
    with get_db() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO translations
            (source_text, source_lang, target_lang, translated_text)
            VALUES (?, ?, ?, ?)
            """,
            data
        )
        conn.commit()