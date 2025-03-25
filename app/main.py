from fastapi import FastAPI, Depends
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from .models import TranslationRequest, TranslationResponse
from .translator import AITranslator
from .dependencies import get_translator
from .crud import get_cached_translations, bulk_save_translations
import os
from typing import List, Dict
app = FastAPI(
    title="AI 翻译服务 API",
    description="基于 LangGraph 和 OpenAI 的多语言翻译服务",
    version="1.0.0",
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/translate", response_model=TranslationResponse)
async def translate_texts(   
    request: TranslationRequest,
    translator: AITranslator = Depends(get_translator)
    ):
    """
    带缓存的翻译接口流程：
    1. 查询数据库缓存
    2. 只发送未缓存的文本到AI翻译
    3. 保存新翻译结果到数据库
    4. 合并返回结果
    """
    if not request.data:
        return []
    
    # 准备所有语言配置
    lang_configs = [
        ("zh-TW", True), ("tr", False), 
        ("th", False), ("ja", False),
        ("ko", False), ("en", False), 
        ("my", False)
    ]
    
    # 初始化结果容器
    results = {item.content: {"key": item.content, "zh": item.content} for item in request.data}
    
    # 处理每种语言
    for target_lang, is_traditional in lang_configs:
        # 1. 查询缓存
        cached = get_cached_translations(
            [item.model_dump() for item in request.data],
            target_lang
        )
        
        # 2. 分离需要翻译的文本
        cached_texts = set(cached.keys())
        to_translate = [
            item for item in request.data 
            if item.content not in cached_texts
        ]
        
        # 3. 调用AI翻译未缓存的文本
        new_translations = []
        if to_translate:
            new_translations = await translator.translate_batch(
                to_translate
            )
            bulk_save_translations(
                [item.model_dump() for item in to_translate],
                new_translations,
                target_lang
            )
        
        # 4. 合并结果
        translations_map = {**cached, **dict(zip(
            [item.content for item in to_translate],
            new_translations
        ))}
        
        for content, data in results.items():
            data[target_lang] = translations_map.get(content)
    
    return list(results.values())

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="AI 翻译服务 API",
        version="1.0.0",
        description="基于 LangGraph 和 OpenAI 的多语言翻译服务",
        routes=app.routes,
    )
    
    # 添加示例请求
    openapi_schema["paths"]["/translate"]["post"]["requestBody"] = {
        "content": {
            "application/json": {
                "example": {
                    "data": [
                        {"content": "语言", "lang": "zh"},
                        {"content": "订单ID", "lang": "zh"}
                    ]
                }
            }
        }
    }
    
    # 添加示例响应
    openapi_schema["paths"]["/translate"]["post"]["responses"]["200"]["content"] = {
        "application/json": {
            "example": {
                "translations": [
                    {
                        "key": "语言",
                        "zh": "语言",
                        "zh-TW": "語言",
                        "tr": "Dil",
                        "th": "ภาษา",
                        "ja": "言語",
                        "ko": "언어",
                        "en": "Language",
                        "my": "ဘာသာစကား"
                    }
                ]
            }
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi