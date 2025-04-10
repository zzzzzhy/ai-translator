from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class TranslationItem(BaseModel):
    content: str
    lang: str

class TranslationRequest(BaseModel):
    data: List[TranslationItem]

class TranslationResult(BaseModel):
    key: str
    zh: Optional[str] = None
    zh_tw: Optional[str] = Field(None, alias="zh-TW") 
    tr: Optional[str] = None
    th: Optional[str] = None
    ja: Optional[str] = None
    ko: Optional[str] = None
    en: Optional[str] = None
    my: Optional[str] = None
    de: Optional[str] = None

class TranslationResponse(BaseModel):
    code: int
    message: str
    data: List[TranslationResult]