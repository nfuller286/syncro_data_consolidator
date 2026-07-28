from typing import Optional, Literal, Union

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

# Define a type alias for the possible client types.
ChatClient = Union[ChatGoogleGenerativeAI, ChatOpenAI]

# Define a type alias for known chat capabilities.
# This makes the overloads explicit and may need to be updated if new
# capabilities are added to config.yaml.
ChatCapability = Literal['lightweight', 'complex', 'general', 'flash']

def get_chat_client(
    capability: ChatCapability,
    config: dict,
    logger
) -> Optional[ChatClient]:
    """
    Factory that returns a client object for a Chat Completion API.
    Reads config to select and configure the correct provider.
    """
    try:
        llm_provider_config = config.get('llm_provider_config')
        if not llm_provider_config:
            logger.error("[AUDIT] Failed to instantiate LLM client. Reason: LLM configuration 'llm_provider_config' not found. Capability: '%s'", capability)
            return None

        active_provider = llm_provider_config.get('active_provider')
        if not active_provider:
            logger.error("[AUDIT] Failed to instantiate LLM client. Reason: No 'active_provider' specified in llm_provider_config. Capability: '%s'", capability)
            return None

        provider_config = llm_provider_config.get(active_provider)
        if not provider_config:
            logger.error("[AUDIT] Failed to instantiate LLM client. Reason: Configuration for active provider '%s' not found. Capability: '%s'", active_provider, capability)
            return None

        model_name = provider_config.get('models', {}).get(capability)
        if not model_name:
            logger.error("[AUDIT] Failed to instantiate LLM client. Reason: Model for capability '%s' not found for provider '%s'.", capability, active_provider)
            return None

        # NOTE: these branches match on the *value* of llm_provider_config.active_provider,
        # which must equal the exact name of its own config block below
        # ('google_gemini' / 'local_llm'). Renaming a block requires renaming
        # its branch here too, and vice versa.
        if active_provider == 'google_gemini':
            api_key = provider_config.get('api_key')
            logger.info(
                "[AUDIT] LLM client instantiated successfully. Capability: '%s', Provider: '%s', Model: '%s'",
                capability, active_provider, model_name
            )
            return ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)

        elif active_provider == 'local_llm':
            base_url = provider_config.get('base_url')
            if not base_url:
                logger.error("[AUDIT] Failed to instantiate LLM client. Reason: 'base_url' not found for provider '%s'. Capability: '%s'", active_provider, capability)
                return None
            api_key = provider_config.get('api_key', 'not-needed')
            logger.info(
                "[AUDIT] LLM client instantiated successfully. Capability: '%s', Provider: '%s', Model: '%s'",
                capability, active_provider, model_name
            )
            return ChatOpenAI(model=model_name, base_url=base_url, api_key=api_key)

        else:
            logger.error("[AUDIT] Failed to instantiate LLM client. Reason: Unsupported active_provider '%s'. Capability: '%s'", active_provider, capability)
            return None

    except KeyError as e:
        logger.error("[AUDIT] Failed to instantiate LLM client due to configuration key error. Capability: '%s', Missing Key: %s", capability, e)
        return None
    except Exception as e:
        logger.error("[AUDIT] Failed to instantiate LLM client due to an unexpected error. Capability: '%s', Error: %s", capability, e)
        return None
