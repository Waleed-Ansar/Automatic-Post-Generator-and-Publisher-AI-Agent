from dotenv import load_dotenv
import os

from langchain_openai import ChatOpenAI


load_dotenv()

API_KEY = os.getenv("DEEP_SEEK_API")
BASE_URL = os.getenv("DEEP_SEEK_URI")

def get_llm():
    return ChatOpenAI(
        model="deepseek-reasoner",
        base_url=BASE_URL,
        api_key=API_KEY,
        temperature=0,
        max_retries=5,
        timeout=60,
        request_timeout=60
    )