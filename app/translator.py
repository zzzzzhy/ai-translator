from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from typing import List, Dict
from .models import TranslationItem, TranslationResult
import asyncio

class AITranslator:
    def __init__(self, api_key: str, model: str = "deepseek",use_proxy: str = None, **kwargs):
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
                # other params...
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
                # organization="...",
                # other params...
            )
        elif model == "google":
            os.environ["GOOGLE_API_KEY"] = api_key
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-pro",
                temperature=0,
                max_tokens=None,
                timeout=None,
                max_retries=2,
                **kwargs
                # other params...
            )
        elif model == "ollama":
                self.llm = OllamaLLM(
                model=model,
                **kwargs
            )
        self._init_chains()

    def _init_chains(self):
        """初始化所有语言的 LCEL 链"""
        self.chains = {
            "zh-TW": self._build_chain("繁体中文", is_traditional=True),
            "tr": self._build_chain("土耳其语"),
            "th": self._build_chain("泰语"),
            "ja": self._build_chain("日语"),
            "ko": self._build_chain("韩语"),
            "en": self._build_chain("英语"),
            "my": self._build_chain("缅甸语")
        }

    def _build_chain(self, language: str, is_traditional: bool = False):
        """构建单语言的 LCEL 翻译链"""
        if is_traditional:
            system_msg = f"你是一位专业{language}翻译，请将以下简体中文批量转换为地道的{language}（台湾/香港用语）"
        else:
            system_msg = f"你是一位专业{language}本地化专家，请将以下中文批量翻译为地道的{language}"

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            ("human", "请翻译以下文本（保持编号不变）：\n\n{texts}")
        ])

        return (
            {"texts": RunnablePassthrough()} 
            | prompt 
            | self.llm 
            | self._parse_output
        )

    async def _parse_output(self, response):
        """解析批量翻译结果"""
        return [
            line.split(". ", 1)[1] if ". " in line else line 
            for line in response.content.split("\n") 
            if line.strip()
        ]
    
    async def translate_batch(self, items: List[TranslationItem]) -> List[TranslationResult]:
        """主翻译方法（LCEL 批量处理）"""
        # 准备待翻译文本（带编号）
        texts_with_numbers = "\n".join(
            f"{idx+1}. {item.content}" 
            for idx, item in enumerate(items)
        )

        # 并行执行所有语言翻译
        tasks = {
            lang: chain.ainvoke(texts_with_numbers)
            for lang, chain in self.chains.items()
        }
        all_results = await asyncio.gather(*tasks.values())

        # 构建最终结果
        results = []
        for idx, item in enumerate(items):
            translated = {
                "key": item.content,
                "zh": item.content,
                **{
                    lang: all_results[i][idx] 
                    for i, lang in enumerate(self.chains.keys())
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