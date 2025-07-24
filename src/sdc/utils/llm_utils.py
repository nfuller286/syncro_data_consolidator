import typing
from typing import Optional, Union, overload, Literal

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

# Define a type alias for known chat capabilities.
# This makes the overloads explicit and may need to be updated if new
# capabilities (e.g., 'super_complex') are added to config.json.
ChatCapability = Literal['lightweight', 'complex']

@overload
def get_llm_client(
    capability: Literal['embedding'],
    config: dict,
    logger
) -> Optional[GoogleGenerativeAIEmbeddings]:
    ...

@overload
def get_llm_client(
    capability: ChatCapability,
    config: dict,
    logger
) -> Optional[ChatGoogleGenerativeAI]:
    ...

def get_llm_client(
    capability: str,
    config: dict,
    logger
) -> Optional[Union[ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings]]:
    """
    Factory function to create and return an LLM client based on configuration.

    Args:
        capability (str): The desired LLM capability (e.g., 'complex', 'embedding').
        config (dict): The main SDC configuration dictionary.
        logger: The SDC logger instance.

    Returns:
        Optional[Union[ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings]]:
            An instantiated LLM client or None if an error occurs or capability is not found.
    """
    try:
        llm_config = config.get('llm_config')
        if not llm_config:
            logger.error("LLM configuration 'llm_config' not found in config.")
            return None

        active_provider = llm_config.get('active_provider')
        if not active_provider:
            logger.error("No 'active_provider' specified in llm_config.")
            return None

        if active_provider == 'google_gemini':
            # Corrected: Use 'google_gemini' instead of 'google_gemini_config'
            google_gemini_config = llm_config.get('google_gemini')
            if not google_gemini_config:
                logger.error("Google Gemini configuration 'google_gemini' not found in llm_config.")
                return None

            api_key = google_gemini_config.get('api_key')
            if not api_key:
                logger.error("API key not found for Google Gemini in google_gemini_config.")
                return None

            models_config = google_gemini_config.get('models')
            if not models_config:
                logger.error("Models configuration 'models' not found for Google Gemini.")
                return None

            model_name = models_config.get(capability)
            if not model_name:
                logger.error(f"Model name for capability '{capability}' not found in Google Gemini models config.")
                return None

            if capability == 'embedding':
                logger.info(f"Instantiating GoogleGenerativeAIEmbeddings client with model: {model_name}")
                return GoogleGenerativeAIEmbeddings(model=model_name, google_api_key=api_key)
            else:
                logger.info(f"Instantiating ChatGoogleGenerativeAI client with model: {model_name}")
                return ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)
        else:
            logger.error(f"Unsupported LLM provider: {active_provider}")
            return None

    except KeyError as e:
        logger.error(f"Configuration error: Missing key {e} in LLM config.")
        return None
    except Exception as e:
        logger.error(f"Error instantiating LLM client for capability '{capability}': {e}")
        return None
