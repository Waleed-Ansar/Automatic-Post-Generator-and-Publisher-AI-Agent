from tavily import TavilyClient

tavily = TavilyClient(api_key="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")


def research_task(query: str) -> str:
    response = tavily.search(
        query=query,
        search_depth="advanced",
        max_results=5,
        include_images=True,
        days=300
    )
    # print(response)
    
    for result in response['results']:
        print(f"Title: {" ".join(result['content'].split(" ")[:100])}")
        print(f"Score: {result['score']}")  # Relevancy score (0.0 to 1.0)
        print(f"URL: {result['url']}")
        
        print("-" * 30)

research_task("what is the benefits of protein?")