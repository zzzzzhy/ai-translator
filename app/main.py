from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware

from .models import TranslationRequest, TranslationResponse, TranslationResult
from .translator import AITranslator
from .crud import get_cached_translations, save_translations_batch
import os
import re
from .database import init_db, mysql_write_pool, mysql_read_pool
import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    # 应用关闭时释放 aiomysql 连接池
    if mysql_write_pool is not None:
        mysql_write_pool.close()
        await mysql_write_pool.wait_closed()
    if mysql_read_pool is not None:
        mysql_read_pool.close()
        await mysql_read_pool.wait_closed()

app = FastAPI(
    title="AI 翻译服务 API",
    description="基于 langchain 和 AI 的多语言翻译服务",
    version="1.0.1",
    lifespan=lifespan,
)

# # 你的密钥，可放到环境变量中
# VALID_API_KEY = "hitosea_devops"
# from fastapi.openapi.docs import get_swagger_ui_html
# from fastapi.responses import JSONResponse
# # 自定义受保护的 docs 路由
# @app.get("/docs", include_in_schema=False)
# async def custom_swagger_ui(request: Request):
#     api_key = request.query_params.get("api_key")

#     if api_key != VALID_API_KEY:
#         # 不返回 swagger，而是拒绝访问
#         raise HTTPException(status_code=403, detail="Forbidden: Invalid API key")
    
#     # 如果通过验证，则返回标准 Swagger 页面
#     return get_swagger_ui_html(
#         openapi_url=f"/openapi.json?api_key={api_key}",
#         title="AITRANS API Docs"
#     )
# @app.get("/openapi.json", include_in_schema=False)
# async def protected_openapi(request: Request):
#     api_key = request.query_params.get("api_key")
#     if api_key != VALID_API_KEY:
#         raise HTTPException(status_code=403, detail="Forbidden: Invalid API key")
#     return JSONResponse(app.openapi())

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 语言代码到中文名映射
LANG_NAME_MAP = {
    "zh": "简体中文",
    "zh-TW": "繁体中文(台湾用语)",
    "tr": "土耳其语",
    "th": "泰语",
    "ja": "日语",
    "ko": "韩语",
    "en": "英语",
    "my": "缅甸语",
    "de": "德语",
    "fr": "法语",
    "es": "西班牙语",
    "it": "意大利语",
    "ru": "俄语",
    "sv": "瑞典语"
    # 可继续扩展
}

def build_prompts(trans_list):
    lang_list = [(code, LANG_NAME_MAP.get(code, code)) for code in trans_list]
    lang_str = "\n".join([f"- {k}: {v}" for k, v in lang_list])
    json_fields = ",".join([f'"{k}": null' for k, _ in lang_list])
    json_fields += ', "id": 序号'
    # print(json_fields)
    system_prompt = f"""你是一位专业的多语言翻译专家，能进行本地化翻译，将文本同时翻译为多种语言:\n{lang_str}\n如果存在多种结果,只需要返回一个"""
    human_prompt = f"""请翻译<content>标签内的文本:\n{{texts}}\n保留换行符(\\n),@字符开始的英文单词保留原内容,按以下json格式返回:\n```
{{{{"data": [{{{{{json_fields}}}}}]}}}}```\n"""
    # print(system_prompt, human_prompt)
    return system_prompt, human_prompt

def remove_all_symbols(text):
    if not isinstance(text, str):
        return text
    return re.sub(r'[^\w]', '', text)


@app.get("/health")
async def health_check():
    return "success"

@app.post("/translate", response_model=TranslationResponse)
async def translate_with_cache(request: TranslationRequest):
    trans_list = request.trans or ["zh","zh-TW","tr","th","ja","ko","en","my","de","sv"]
    custom_system_prompt, custom_human_prompt = build_prompts(trans_list)
    translator = AITranslator(
        os.getenv("OPENAI_API_KEY"),
        os.getenv("MODEL_VENDER"),
        os.getenv("MODEL"),
        os.getenv("PROXY"),
        custom_system_prompt,
        custom_human_prompt,
        reasoning_effort="minimal"
    )
    # 1. 准备数据
    source_texts = [item.content for item in request.data]
    source_lang = request.data[0].lang if request.data else "zh"
    if source_lang == "cn":
        source_lang = "zh"
    print("request------", request.data,request.force_trans)
    # 2. 查询缓存
    if request.force_trans:
        cached = {}
    else:
        cached = await get_cached_translations(source_texts, source_lang, trans_list)
    print("cached------", cached)
    # 3. 分离需要翻译的文本
    to_translate = [
        item for item in request.data
        if item.content not in cached
    ]
    for idx, item in enumerate(to_translate):
        setattr(item, "id", idx)
    print(to_translate)
    # 4. 调用AI翻译
    new_translations = {}
    if to_translate:
        raw_results = await translator.translate_batch(to_translate)
        if not raw_results:
            return {"code": 500, "message": "翻译失败", "data": []}
        for raw_item in raw_results:
            for item in to_translate:
                if item.id == raw_item.get("id"):
                    new_translations[item.content]= {k: v for k, v in raw_item.items() if k != "id"}
            
        # 5. 保存新结果
        try:
            save_results = []
            valid_translations = []
            for item in to_translate:
                if item.content in (new_translations.get(item.content) or {}).values():
                    save_results.append(item.model_dump())
                    valid_translations.append(new_translations.get(item.content))
            await save_translations_batch(
                save_results, valid_translations, trans_list
            )
        except Exception as e:
            print("保存翻译结果失败:", e)
            # 如果保存失败，仍然返回翻译结果
    # 6. 合并结果
    all_translations = {**cached, **new_translations}
    print(all_translations,new_translations,cached)
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
                    "force_trans": False,
                    "trans": ["zh","en"]
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
                        "fr": "法语",
                        "es": "西班牙语",
                        "it": "意大利语",
                        "ru": "俄语",
                        "sv": "瑞典语"
                    }
                ]
            }
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
