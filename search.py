from dotenv import load_dotenv
import os

from langchain.agents import create_agent
from langchain_core.tools import tool
from serpapi.google_search import GoogleSearch
from tavily import TavilyClient

from llm import get_llm
from prompts import SEARCH_AGENT_PROMPT


load_dotenv()

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

tavily = TavilyClient(api_key=TAVILY_API_KEY)

@tool
def research_task(query: str) -> str:
    """
    Performs a web search using the Search API and returns the top results.
    Do not search more than 5 times for one query.
    """
    print("Search...")

    response = tavily.search(
        query=query,
        search_depth="advanced",
        max_results=5,
        include_images=True,
        days=300
    )
    
    data = []
    for i, result in enumerate(response['results']):
        res = {
            "Result Number:": i,
            "Title:": result.get("title", []),
            "Description:": " ".join(result.get('content', []).split(" ")[:100]),
            "Link": result.get("url", [])
        }
        
        data.append(res)
    
    return data

# @tool
# def research_task(query: str) -> str:
#     """
#     Performs a web search using the Search API and returns the top results.
#     Do not search more than 5 times for one query.
#     """
#     print("search triggered")

#     itr = 0
#     params = {
#         "q": query,
#         "api_key": SERPAPI_API_KEY,
#         "num": 10,
#         "tbs": "qdr:y"
#     }

#     search = GoogleSearch(params)
#     results = search.get_dict()

#     data = []
#     # print("Results Number:", len(results.get("organic_results")))
#     for i, result in enumerate(results.get("organic_results", []), start=1):
#         res = {
#             "Result Number:": i,
#             "Title:": result.get("title", []),
#             "Description:": result.get("snippet", []),
#             "Link": result.get("link", [])
#         }
        
#         data.append(res)

#     return data


search_agent = create_agent(
    model=get_llm(),
    tools=[
        research_task
    ],
    system_prompt=SEARCH_AGENT_PROMPT,
    # debug=True
    )