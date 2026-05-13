from langchain_core.tools import tool

from db import database_agent
from search import search_agent
from render_post import post_creation_agent
from post import facebook_posting_agent

@tool
def AskDatabaseAgent(question: str) -> str:
    """
    Ask the database specialist sub-agent to answer or perform a database task.
    Use this for questions involving PostgreSQL data.
    """
    result = database_agent.invoke({
        "messages": [
            {
                "role": "user",
                "content": question
            }
        ]
    })

    return result["messages"][-1].content

@tool
def AskSearchAgent(question: str) -> str:
    """
    Ask the search specialist sub-agent to find, inspect, and summarize information.
    Use this for questions involving local files, documents, logs, code files,
    project files, web research, or unknown information sources.
    """
    result = search_agent.invoke({
        "messages": [
            {
                "role": "user",
                "content": question
            }
        ]
    })

    return result["messages"][-1].content

@tool
def AskPostCreationAgent(question: str) -> str:
    """
    Ask the social media post creation sub-agent to generate a 1080x1080 social media post.

    Use this tool whenever the user asks to:
    - create a social media post
    - generate a post image
    - design a post
    - make an Instagram/Facebook/LinkedIn post
    - create a post using Python templates
    - generate post content with heading, subheading, content, CTA/follow-up, and link

    The post creation agent can use these template names:

    1. Neon Style
    2. Editorial Card
    3. Gradient Wave
    4. Retro Notice
    5. Glass Panel
    6. Warning Stripes
    7. Orbit Badge
    8. Diagonal Split
    9. Blueprint Grid
    10. Feed Alert

    If the user does not specify a template, the agent should choose the best template
    based on the topic or randomly select one.
    """
    result = post_creation_agent.invoke({
        "messages": [
            {
                "role": "user",
                "content": question
            }
        ]
    })

    return result["messages"][-1].content

@tool
def AskFacebookPostingAgent(question: str) -> str:
    """
    Ask the Facebook posting sub-agent to post an image with a caption to a Facebook Page.
    Use this when the user wants to publish an existing/generated image to Facebook.
    """
    if facebook_posting_agent is None:
        return (
            "Facebook posting agent is not initialized. "
            "Make sure langchain is installed, llm.py exists, get_llm() works, "
            "create_agent is available, and post_facebook_image_with_caption is registered."
        )

    result = facebook_posting_agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": question,
                }
            ]
        }
    )

    return result["messages"][-1].content

Agents = [AskSearchAgent, AskPostCreationAgent, AskFacebookPostingAgent]