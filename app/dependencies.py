from .translator import AITranslator
import os
def get_translator():
    # 从环境变量获取 OpenAI API 密钥
    api_key = os.getenv("OPENAI_API_KEY")
    # if not api_key:
    #     raise ValueError("OPENAI_API_KEY 环境变量未设置")
    
    return AITranslator(api_key=api_key)