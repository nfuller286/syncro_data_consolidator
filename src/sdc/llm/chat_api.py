from typing import Optional, Literal

from langchain_google_genai import ChatGoogleGenerativeAI

# Define a type alias for known chat capabilities.
# This makes the overloads explicit and may need to be updated if new
# capabilities are added to config.json.
ChatCapability = Literal['lightweight', 'complex', 'general', 'flash']

def get_chat_client(
    capability: ChatCapability,
    config: dict,
    logger
) -> Optional[ChatGoogleGenerativeAI]:
    """
    Factory that returns a client object for a Chat Completion API.
    Reads config to select and configure the correct provider.
    """
    try:
        llm_config = config.get('llm_config')
        if not llm_config:
            logger.error("[AUDIT] Failed to instantiate LLM client. Reason: LLM configuration 'llm_config' not found. Capability: '%s'", capability)
            return None
 
        active_provider = llm_config.get('active_provider')
        if not active_provider:
            logger.error("[AUDIT] Failed to instantiate LLM client. Reason: No 'active_provider' specified in llm_config. Capability: '%s'", capability)
            return None
 
        provider_config = llm_config.get(active_provider)
        if not provider_config:
            logger.error("[AUDIT] Failed to instantiate LLM client. Reason: Configuration for active provider '%s' not found. Capability: '%s'", active_provider, capability)
            return None
 
        api_key = provider_config.get('api_key')
        model_name = provider_config.get('models', {}).get(capability)
 
        if not model_name:
            logger.error("[AUDIT] Failed to instantiate LLM client. Reason: Model for capability '%s' not found for provider '%s'.", capability, active_provider)
            return None
 
        # Using format-string style for clarity and to handle variables cleanly.
        logger.info(
            "[AUDIT] LLM client instantiated successfully. Capability: '%s', Provider: '%s', Model: '%s'",
            capability, active_provider, model_name
        )
        return ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)
 
    except KeyError as e:
        logger.error("[AUDIT] Failed to instantiate LLM client due to configuration key error. Capability: '%s', Missing Key: %s", capability, e)
        return None
    except Exception as e:
        logger.error("[AUDIT] Failed to instantiate LLM client due to an unexpected error. Capability: '%s', Error: %s", capability, e)
        return None
