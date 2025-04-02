from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from typing import List, Dict
from .models import TranslationItem, TranslationResult
import os
import asyncio

class AITranslator:
    def __init__(self, api_key: str, model: str = "deepseek", use_proxy: str = None, **kwargs):
        if use_proxy:
            os.environ["https_proxy"] = use_proxy
            os.environ["http_proxy"] = use_proxy
        if model == "deepseek":
            self.llm = ChatDeepSeek(
                model="deepseek-chat",
                temperature=0,
                max_tokens=None,
                timeout=None,
                max_retries=2,
                api_key=api_key,
                streaming=False,
                **kwargs,
            )
        elif model == "openai":
            self.llm = ChatOpenAI(
                model="gpt-4o",
                temperature=0,
                max_tokens=None,
                timeout=None,
                max_retries=2,
                api_key=api_key,
                **kwargs,
            )
        elif model == "google":
            os.environ["GOOGLE_API_KEY"] = api_key
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                temperature=0,
                max_tokens=None,
                timeout=None,
                max_retries=2,
                **kwargs
            )
        elif model == "ollama":
            self.llm = OllamaLLM(
                model=model,
                **kwargs
            )
        elif model == "azure":
            os.environ["AZURE_OPENAI_API_KEY"] = api_key
            os.environ["AZURE_OPENAI_ENDPOINT"] = "https://ttpos.openai.azure.com"
            self.llm = AzureChatOpenAI(
                azure_deployment="gpt-4o",
                api_version="2024-08-01-preview",
                temperature=0,
                max_tokens=None,
                timeout=None,
                max_retries=2,
            )
        self._init_chain()

    def _init_chain(self):
        """初始化单请求多语言翻译链"""
        system_msg = """你是一位专业的多语言翻译专家,对菜名有专业的理解,请将以下中文文本同时翻译为多种语言：
- 繁体中文(台湾/香港用语)
- 土耳其语
- 泰语
- 日语
- 韩语
- 英语
- 缅甸语

请按照指定格式返回结果，保持编号不变。"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            ("human", "请翻译以下文本（保持编号不变）：\n\n{texts}\n\n请按以下格式返回：\n编号. 原文\n  zh-TW: 繁体中文翻译\n  tr: 土耳其语翻译\n  th: 泰语翻译\n  ja: 日语翻译\n  ko: 韩语翻译\n  en: 英语翻译\n  my: 缅甸语翻译")
        ])

        self.chain = (
            {"texts": RunnablePassthrough()} 
            | prompt 
            | self.llm 
            | self._parse_output
        )

    async def _parse_output(self, response):
        """解析多语言批量翻译结果"""
        results = {}
        current_id = None
        
        for line in response.content.split("\n"):
            line = line.strip()
            if not line:
                continue
                
            # 检查是否是编号行
            if line[0].isdigit() and ". " in line:
                parts = line.split(". ", 1)
                current_id = int(parts[0]) - 1  # 转换为0-based索引
                results[current_id] = {"zh": parts[1]}
            # 检查是否是翻译行
            elif ": " in line and current_id is not None:
                lang, translation = line.split(": ", 1)
                results[current_id][lang.strip()] = translation.strip()
        
        # 转换为按语言分组的格式
        translations = {}
        for lang in ["zh-TW", "tr", "th", "ja", "ko", "en", "my"]:
            translations[lang] = [results[i][lang] for i in sorted(results.keys())]
            
        return translations
    
    async def translate_batch(self, items: List[TranslationItem]) -> List[TranslationResult]:
        """主翻译方法（单请求批量处理）"""
        # 准备待翻译文本（带编号）
        texts_with_numbers = "\n".join(
            f"{idx+1}. {item.content}" 
            for idx, item in enumerate(items)
        )

        # 执行翻译
        all_results = await self.chain.ainvoke(texts_with_numbers)
        print("all_results------", all_results)
        # 构建最终结果
        results = []
        for idx, item in enumerate(items):
            translated = {
                "key": item.content,
                "zh": item.content,
                **{
                    lang: all_results[lang][idx]
                    for lang in ["zh-TW", "tr", "th", "ja", "ko", "en", "my"]
                }
            }
            results.append(TranslationResult(**translated))
        
        return results
    
    async def translate_large_batch(self, items: List[TranslationItem], batch_size=50):
        """处理超大批量数据"""
        results = []
        for i in range(0, len(items), batch_size):
            batch = items[i:i+batch_size]
            results += await self.translate_batch(batch)
        return results