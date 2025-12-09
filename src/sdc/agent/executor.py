# src/sdc/agent/executor.py

from langchain.agents import create_agent
from langchain import hub
from sdc.agent.tools import get_tools
from sdc.llm.chat_api import get_chat_client
from sdc.utils.config_loader import load_config
from sdc.utils.sdc_logger import get_sdc_logger

def create_agent_executor():
    """
    Creates and returns an agent executor.
    """
    config = load_config()
    if not config:
        raise ValueError("Failed to load configuration.")

    logger = get_sdc_logger(__name__, config)

    tools = get_tools()
    llm = get_chat_client('complex', config, logger)

    # Get the prompt to use - you can modify this!
    prompt = hub.pull("hwchase17/react")

    agent = create_agent(llm, tools, prompt)
    
    return agent

def run_query(query: str):
    """
    Runs a query through the agent executor.
    """
    agent_executor = create_agent_executor()
    result = agent_executor.invoke({"input": query})
    return result
