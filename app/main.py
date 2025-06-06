from fastapi import FastAPI, Depends
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from .models import TranslationRequest, TranslationResponse, TranslationResult
from .translator import AITranslator
from .crud import get_cached_translations, save_translations_batch
import os
from typing import List, Dict
from .database import init_db

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
system_prompt = """你是一位专业的多语言翻译专家,对菜名有专业的理解,能进行本地化翻译,将文本同时翻译为多种语言:
- zh: 简体中文
- zh-TW: 繁体中文(台湾用语)
- tr: 土耳其语
- th: 泰语
- ja: 日语
- ko: 韩语
- en: 英语
- my: 缅甸语
- de: 德语
如果存在多种结果,只需要返回一个"""
human_prompt = """请翻译以下文本:
{texts}
,保持编号不变,保留<end>标签,保留换行符(\n),不要添加翻译标识,@字符开始的英文单词保留原内容,严格按以下格式返回:
编号:-> \n<end>  zh: null<end>  zh-TW: null<end>  tr: null<end>  th: null<end>  ja: null<end>  ko: null<end>  en: null<end>  my: null<end>  de: null<end>"""
        
translator = AITranslator(os.getenv("OPENAI_API_KEY"), os.getenv("MODEL"), os.getenv("PROXY"),system_prompt,human_prompt)

@app.post("/translate", response_model=TranslationResponse)
async def translate_with_cache(request: TranslationRequest):
    # 1. 准备数据
    source_texts = [item.content for item in request.data]
    source_lang = request.data[0].lang if request.data else "zh"
    print("request------", request.data,request.is_food)
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
                lang: getattr(result, "zh_tw" if lang == "zh-TW" else lang)
                for lang in ["zh", "zh-TW", "en", "ja", "ko", "tr", "th", "my", "de"]
            }
            for item, result in zip(to_translate, raw_results)
        }
        if request.is_food:
            # 5. 保存新结果
            try:
                save_results = []
                for item in to_translate:
                    if len(new_translations.get(item.content)[item.lang]) != len(item.content):
                        print("翻译长度不一致", item.content, new_translations.get(item.content)[item.lang], item.lang)
                        continue
                    else:
                        save_results.append(item.model_dump())
                save_translations_batch(
                    save_results, list(new_translations.values())
                )
            except Exception as e:
                print("保存翻译结果失败:", e)
                # 如果保存失败，仍然返回翻译结果
    # 6. 合并结果
    all_translations = {**cached, **new_translations}
    return {"code": 200, "message": "success", "data": [
        TranslationResult(
            key=text,
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
                    ],
                    "is_food": True
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
                        "de": "Sprache",
                    }
                ]
            }
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
