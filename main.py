import logging

from langchain.agents import create_agent
import langchain
from langgraph.checkpoint.memory import InMemorySaver

from llm import get_llm
from agents import Agents
from prompts import COORDINATOR_AGENT_PROMPT


checkpointer = InMemorySaver()

MAX_RETRIES = 5

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

def run_agent(query: str):
    THREAD_ID = "anonymus-main-chat-1"
    print("main function called")

    i = 0
    ERROR = ""
    while i < MAX_RETRIES:
        try:
            if ERROR != "":
                result = main_agent.invoke(
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": query
                            }
                        ]
                    },
                    config={
                        "configurable": {
                            "thread_id": THREAD_ID
                        }
                    }
                )

                return result["messages"][-1].content
            
            else:
                result = main_agent.invoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": query + ERROR + "Try a different approach."
                        }
                    ]
                },
                config={
                    "configurable": {
                        "thread_id": THREAD_ID
                    }
                }
            )

            return result["messages"][-1].content

        except Exception as e:
            i = i + 1
            ERROR = f"Got error {e} while execution."
            logging.warning(e)
            return False