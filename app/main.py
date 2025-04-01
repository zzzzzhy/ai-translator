from fastapi import FastAPI, Depends
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from .models import TranslationRequest, TranslationResponse, TranslationResult
from .translator import AITranslator
from .dependencies import get_translator
from .crud import get_cached_translations, save_translations_batch
import os
from typing import List, Dict
from app.database import init_db

init_db()
app = FastAPI(
    title="AI 翻译服务 API",
    description="基于 langchain 和 AI 的多语言翻译服务",
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
translator = AITranslator(Depends(get_translator))


@app.post("/translate", response_model=TranslationResponse)
async def translate_with_cache(request: TranslationRequest):
    # 1. 准备数据
    source_texts = [item.content for item in request.data]
    source_lang = request.data[0].lang if request.data else "zh"

    # 2. 查询缓存
    cached = get_cached_translations(source_texts, source_lang)
    print("cached------", cached)
    # 3. 分离需要翻译的文本
    to_translate = [item for item in request.data if item.content not in cached]

    # 4. 调用AI翻译
    new_translations = {}
    if to_translate:
        raw_results = await translator.translate_batch(to_translate)
        # 转换格式：{"文本": {"en": "翻译", "ja": "翻訳"...}}
        new_translations = {
            item.content: {
                lang: getattr(result, lang)
                for lang in ["zh_tw", "en", "ja", "ko", "tr", "th", "my"]
            }
            for item, result in zip(to_translate, raw_results)
        }
        # 5. 保存新结果
        save_translations_batch(
            [item.dict() for item in to_translate], list(new_translations.values())
        )

    # 6. 合并结果
    all_translations = {**cached, **new_translations}
    return {"code": 200, "message": "success", "data": [
        TranslationResult(
            key=text,
            zh=text,
            **all_translations.get(text, {})
        )
        for text in source_texts
    ]}


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
                        {"content": "订单ID", "lang": "zh"},
                    ]
                }
            }
        }
    }

    # 添加示例响应
    openapi_schema["paths"]["/translate"]["post"]["responses"]["200"]["content"] = {
        "application/json": {
            "example": {
                "code": 200,
                "message": "success",
                "data": [
                    {
                        "key": "语言",
                        "zh": "语言",
                        "zh-TW": "語言",
                        "tr": "Dil",
                        "th": "ภาษา",
                        "ja": "言語",
                        "ko": "언어",
                        "en": "Language",
                        "my": "ဘာသာစကား",
                    }
                ]
            }
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
