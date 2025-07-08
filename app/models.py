from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, model_validator
from typing_extensions import Annotated

class TranslationItem(BaseModel):
    content: str
    lang: str
    id: Optional[int] = Field(None)

class TranslationRequest(BaseModel):
    data: List[TranslationItem]
    force_trans: Optional[bool] = False
    trans: Optional[List[str]] = []

class TranslationResult(BaseModel):
    key: str
    # 支持所有在 LANG_NAME_MAP 中定义的语言
    # zh: Optional[str] = None
    # zh_tw: Optional[str] = Field(None, alias="zh-TW")
    # tr: Optional[str] = None
    # th: Optional[str] = None
    # ja: Optional[str] = None
    # ko: Optional[str] = None
    # en: Optional[str] = None
    # my: Optional[str] = None
    # de: Optional[str] = None
    # fr: Optional[str] = None
    # es: Optional[str] = None
    # it: Optional[str] = None
    # ru: Optional[str] = None
    
    # 允许额外的语言字段
    model_config = {"extra": "allow"}

class TranslationResponse(BaseModel):
    code: int
    message: str
    data: List[TranslationResult]