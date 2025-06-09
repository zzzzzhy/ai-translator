import json
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
from langchain_core.runnables import RunnableLambda

def print_messages(messages):
    print("渲染后的 Prompt Messages:",messages)
    return messages

class AITranslator:
    def __init__(self, api_key: str, model_vender: str = "openai", model: str = "gpt-4.1-mini",  use_proxy: str = None, system_prompt: str = None, human_prompt: str = None, **kwargs):
        if use_proxy:
            os.environ["https_proxy"] = use_proxy
            os.environ["http_proxy"] = use_proxy
        if model_vender == "deepseek":
            self.llm = ChatDeepSeek(
                model=model,
                temperature=0,
                max_tokens=None,
                timeout=None,
                max_retries=2,
                api_key=api_key,
                streaming=False,
                **kwargs,
            )
        elif model_vender == "openai":
            self.llm = ChatOpenAI(
                model=model,
                temperature=0,
                max_tokens=None,
                timeout=None,
                max_retries=2,
                api_key=api_key,
                **kwargs,
            )
        elif model_vender == "google":
            os.environ["GOOGLE_API_KEY"] = api_key
            self.llm = ChatGoogleGenerativeAI(
                model=model,
                temperature=0,
                max_tokens=None,
                timeout=None,
                max_retries=2,
                **kwargs
            )
        elif model_vender == "ollama":
            self.llm = OllamaLLM(
                model=model,
                **kwargs
            )
        elif model_vender == "azure":
            os.environ["AZURE_OPENAI_API_KEY"] = api_key
            os.environ["AZURE_OPENAI_ENDPOINT"] = "https://ttpos.openai.azure.com"
            self.llm = AzureChatOpenAI(
                azure_deployment=model,
                api_version="2025-04-01-preview",
                temperature=0,
                max_tokens=None,
                timeout=None,
                max_retries=2,
            )
        self._init_chain(system_prompt, human_prompt)
    # 插入一个打印消息的中间件

    def _init_chain(self,system_prompt: str = None, human_prompt: str = None):
        """初始化单请求多语言翻译链"""
        if not system_prompt:
            raise ValueError("system_prompt is required")
        if not human_prompt:
            raise ValueError("human_prompt is required")
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt)
        ])
        print_node = RunnableLambda(print_messages)
        self.chain = (
            {"texts": RunnablePassthrough()} 
            | prompt 
            | print_node
            | self.llm 
            # | self._parse_output
        )

    # async def _parse_output(self, response):
    #     """解析多语言批量翻译结果"""
    #     results = {}
    #     current_id = None
    #     print("response------", response.content)
    #     for line in response.content.split("<end>"):
    #         line = line.strip()
    #         if not line:
    #             continue
    #         # 检查是否是编号行
    #         if ":->" in line:
    #             parts = line.split(":->", 1)
    #             current_id = int(parts[0][-1]) - 1  # 转换为0-based索引
    #             results[current_id] = {}
    #         # 检查是否是翻译行
    #         elif ": " in line and current_id is not None:
    #             for lang in ["zh", "zh-TW", "tr", "th", "ja", "ko", "en", "my", "de"]:
    #                 if line.startswith(lang + ":"):
    #                     translation = line.split(lang + ":", 1)[1]
    #                     results[current_id][lang] = translation.strip()
    #             # lang, translation = line.split(": ", 1)
    #             # results[current_id][lang.strip()] = translation.strip()
        
    #     # 转换为按语言分组的格式
    #     translations = {}
    #     for lang in ["zh", "zh-TW", "tr", "th", "ja", "ko", "en", "my", "de"]:
    #         translations[lang] = [results[i][lang] for i in sorted(results.keys())]
            
    #     return translations
    
    async def translate_batch(self, items: List[TranslationItem]) -> List[TranslationResult]:
        """主翻译方法（单请求批量处理）"""
        # 准备待翻译文本（带编号）
        texts_with_numbers = "\n".join(
            f"{idx+1}: <content>{item.content}<content>" 
            for idx, item in enumerate(items)
        )
        print(texts_with_numbers)
        # 执行翻译
        all_results = await self.chain.ainvoke(texts_with_numbers)
        print("all_results------", all_results)
        try:
            data = json.loads(all_results.content)
            results = data.get("data")
            return results
        except Exception as e:
            return []
        
        # for idx, item in enumerate(items):
        #     translated = {
        #         "key": item.content,
        #         **{
        #             lang: all_results[lang][idx]
        #             for lang in ["zh", "zh-TW", "tr", "th", "ja", "ko", "en", "my", "de"]
        #         }
        #     }
        #     results.append(TranslationResult(**translated))
        
        
    
    async def translate_large_batch(self, items: List[TranslationItem], batch_size=50):
        """处理超大批量数据"""
        results = []
        for i in range(0, len(items), batch_size):
            batch = items[i:i+batch_size]
            results += await self.translate_batch(batch)
        return results