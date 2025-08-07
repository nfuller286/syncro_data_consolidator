import os
import sys

# Add the 'src' directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from sdc.utils.config_loader import load_config
from sdc.utils.sdc_logger import get_sdc_logger
from sdc.utils.llm_utils import get_llm_client

def main():
    """Main function to test LLM connectivity."""
    # Load configuration and logger
    config = load_config()
    logger = get_sdc_logger('test_llm', config)

    logger.info("--- Starting Standalone LLM Utility Test ---")

    # Get the LLM client for complex tasks (chat)
    logger.info("Attempting to get 'complex' LLM client...")
    llm_client = get_llm_client('complex', config, logger)

    if not llm_client:
        logger.error("Failed to instantiate LLM client. Check config and API keys.")
        logger.info("--- LLM Test Failed ---")
        return

    logger.info(f"Successfully instantiated LLM client: {type(llm_client).__name__}")

    # Define a test prompt
    test_prompt = "What is the result of 1 + 1? Respond with only the numerical answer."
    logger.info(f"Sending test prompt: '{test_prompt}'")

    try:
        # Invoke the LLM
        response = llm_client.invoke(test_prompt)
        
        # The response object from LangChain has a 'content' attribute
        if hasattr(response, 'content'):
            logger.info(f"LLM Response: {response.content}")
            if '2' in response.content:
                logger.info("--- LLM Test Successful ---")
            else:
                logger.warning("LLM responded, but the answer was not as expected.")
                logger.info("--- LLM Test Completed with Warnings ---")
        else:
            logger.error(f"LLM response object did not have 'content' attribute. Full response: {response}")
            logger.info("--- LLM Test Failed ---")

    except Exception as e:
        logger.error(f"An error occurred while invoking the LLM: {e}", exc_info=True)
        logger.info("--- LLM Test Failed ---")

if __name__ == "__main__":
    main()

