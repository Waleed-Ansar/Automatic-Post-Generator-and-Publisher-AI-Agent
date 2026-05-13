import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from langchain.tools import tool
from langchain.agents import create_agent

from llm import get_llm
from prompts import FACEBOOK_POSTING_AGENT_PROMPT


load_dotenv()

GRAPH_VERSION = "v24.0"
PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
PAGE_ACCESS_TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")

@tool
def post_image_to_facebook_page(image_path: str, caption_path: str) -> dict:
    """
    Post a local image with a caption to a Facebook Page.

    Required:
    - image_path: local image path, for example posts/post.png
    - caption_path: path to a file containing the text caption for the Facebook post

    Optional:
    - page_id: Facebook Page ID. If not provided, FB_PAGE_ID is used from .env

    Environment variables:
    - FB_PAGE_ID
    - FB_PAGE_ACCESS_TOKEN
    - FB_GRAPH_VERSION optional, default v24.0
    """
    image_path = image_path.split("\n")[-1].replace("_", " ")
    print("PATHS:", image_path, caption_path)
    path = Path(image_path)
    
    with open(caption_path, "rb") as f:
        MESSAGE = f.read().decode("utf-8", errors="ignore")

    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    url = f"https://graph.facebook.com/v24.0/{PAGE_ID}/photos"

    with path.open("rb") as image_file:
        response = requests.post(
            url,
            data={
                "message": MESSAGE,
                "access_token": PAGE_ACCESS_TOKEN,
                "published": "true",
            },
            files={
                "source": image_file,
            },
            timeout=120,
        )

    try:
        result = response.json()
    except ValueError:
        raise RuntimeError(f"Non-JSON response: {response.text}")

    if not response.ok:
        raise RuntimeError(f"Facebook API error: {result}")

    return result


facebook_posting_agent = None
if create_agent is not None and get_llm is not None:
    try:
        facebook_posting_agent = create_agent(
            model=get_llm(), 
            tools=[post_image_to_facebook_page], 
            system_prompt=FACEBOOK_POSTING_AGENT_PROMPT,
            # debug=True
        )

    except Exception:
        facebook_posting_agent = None


@tool
def AskFacebookPostingAgent(question: str) -> str:
    """
    Ask the Facebook posting sub-agent to post an image with a caption to a Facebook Page.
    Use this when the user wants to publish an existing/generated image to Facebook.
    """
    if facebook_posting_agent is None:
        return "Post creation agent is not initialized. Make sure langchain is installed, llm.py exists, get_llm() works, and create_agent is available."
    result = facebook_posting_agent.invoke({"messages": [{"role": "user", "content": question}]})
    return result["messages"][-1].content