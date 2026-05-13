from dotenv import load_dotenv
import os

from langchain.agents import create_agent
from langchain_core.tools import tool
from serpapi.google_search import GoogleSearch

from llm import get_llm
from prompts import SEARCH_AGENT_PROMPT


load_dotenv()

API_KEY = os.getenv("SERPAPI_API_KEY")


@tool
def research_task(query: str) -> str:
    """
    Performs a web search using the Google Search API and returns the top results.
    Do not search more than 5 times for one query.
    """
    itr = 0
    params = {
        "q": query,
        "api_key": API_KEY,
        "num": 10,
        "tbs": "qdr:y"
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    data = []
    # print("Results Number:", len(results.get("organic_results")))
    for i, result in enumerate(results.get("organic_results", []), start=1):
        res = {
            "Result Number:": i,
            "Title:": result["title"],
            "Description:": result["snippet"],
            "Link": result["link"]
        }
        
        data.append(res)

    itr = itr + 1
    print(itr)
    return data


search_agent = create_agent(
    model=get_llm(),
    tools=[
        research_task
    ],
    system_prompt=SEARCH_AGENT_PROMPT,
    # debug=True
    )