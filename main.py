from langchain.agents import create_agent
import langchain
from langsmith import Client
from langgraph.checkpoint.memory import InMemorySaver

from llm import get_llm
from agents import Agents
from prompts import COORDINATOR_AGENT_PROMPT

client = Client()

checkpointer = InMemorySaver()

print(f"LangChain version: {langchain.__version__}")
    
# ---- Sub-agent 1: Research Agent ----
main_agent = create_agent(
    model=get_llm(),
    tools=Agents,
    system_prompt = COORDINATOR_AGENT_PROMPT,
        checkpointer=checkpointer,
        # debug=True
    )

# ---- Run Multi-Agent Workflow ----

THREAD_ID = "waleed-main-chat-1"

while True:
    user_input = input("Enter Query: ")

    if user_input.lower() == "x":
        break

    result = main_agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": user_input
                }
            ]
        },
        config={
            "configurable": {
                "thread_id": THREAD_ID
            }
        }
    )

    print("\nFinal Result:")
    print(result["messages"][-1].content)
    print()