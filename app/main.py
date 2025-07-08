from fastapi import FastAPI, Depends
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from .models import TranslationRequest, TranslationResponse, TranslationResult
from .translator import AITranslator
from .crud import get_cached_translations, save_translations_batch
import os
import re
from .database import init_db

init_db()
app = FastAPI(
    title="AI 翻译服务 API",
    description="基于 langchain 和 AI 的多语言翻译服务",
    version="1.0.1",
)

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
    "sv-SE": "瑞典语"
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
    trans_list = request.trans or ["zh","zh-TW","tr","th","ja","ko","en","my","de"]
    print(trans_list)
    custom_system_prompt, custom_human_prompt = build_prompts(trans_list)
    translator = AITranslator(
        os.getenv("OPENAI_API_KEY"),
        os.getenv("MODEL_VENDER"),
        os.getenv("MODEL"),
        os.getenv("PROXY"),
        custom_system_prompt,
        custom_human_prompt
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
        cached = get_cached_translations(source_texts, source_lang, trans_list)
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
                    new_translations[item.content]= {k: v for k, v in raw_item.items() if k != "id"
        }
        # content_to_translations = {}
        # for item in raw_results:
        #     for value in item.values():
        #         content_to_translations[value] = item
        
        # # 2. 遍历 b，检查 content 是否在 content_to_translations 中
        # try:
        #     normalized_content = {
        #         remove_all_symbols(k): v for k, v in content_to_translations.items()
        #     }
        #     print(normalized_content)
        #     new_translations = {
        #         item.content: normalized_content[remove_all_symbols(item.content)]
        #         for item in to_translate
        #         if item.id == normalized_content
        #     }
        #     print(new_translations)
        # except Exception as e:
        #     print("预处理翻译内容失败:", e)
        #     new_translations = {
        #         item.content: content_to_translations[item.content]
        #         for item in to_translate
        #         if item.content in content_to_translations
        #     }
            
        # 5. 保存新结果
        try:
            save_results = []
            for item in to_translate:
                # if len(new_translations.get(item.content)[source_lang]) != len(item.content):
                #     print("翻译长度不一致", item.content, new_translations.get(item.content)[source_lang], source_lang)
                #     continue
                # else:
                save_results.append(item.model_dump())
            save_translations_batch(
                save_results, list(new_translations.values()), trans_list
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
                    }
                ]
            }
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
