# -*- coding: utf-8 -*-
"""Factory for creating embedding clients."""

def get_embedding_client(config, logger):
    """
    Factory function to get an embedding client based on the configuration.

    Args:
        config (dict): The application configuration.
        logger: The logger instance.

    Returns:
        An instance of an embedding client (e.g., HuggingFaceEmbeddings) or None if initialization fails.
    """
    embedding_config = config.get('embedding_config', {})
    active_provider = embedding_config.get('active_provider')
    
    logger.info(f"Attempting to create embedding client for provider: {active_provider}")

    if active_provider == 'local':
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            provider_config = embedding_config.get('providers', {}).get('local', {})
            model_name = provider_config.get('model_name')
            device = provider_config.get('device', 'cpu')
            
            if not model_name:
                logger.error("Model name for local HuggingFace embeddings is not configured.")
                return None
                
            logger.info(f"Initializing HuggingFaceEmbeddings with model: {model_name} on device: {device}")
            return HuggingFaceEmbeddings(model_name=model_name, model_kwargs={'device': device})

        except ImportError:
            logger.error("The 'langchain-huggingface' package is not installed. Please install it with: pip install langchain-huggingface")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize HuggingFace embeddings: {e}")
            return None

    elif active_provider == 'openai':
        try:
            from langchain_openai import OpenAIEmbeddings
            provider_config = embedding_config.get('providers', {}).get('openai', {})
            model_name = provider_config.get('model_name')
            
            if not model_name:
                logger.error("Model name for OpenAI embeddings is not configured.")
                return None
            
            # Note: OpenAI API key is typically handled by environment variables, 
            # which langchain_openai checks automatically.
            logger.info(f"Initializing OpenAIEmbeddings with model: {model_name}")
            return OpenAIEmbeddings(model=model_name)
            
        except ImportError:
            logger.error("The 'langchain-openai' package is not installed. Please install it with: pip install langchain-openai")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI embeddings: {e}")
            return None
            
    else:
        logger.error(f"Unsupported embedding provider: {active_provider}")
        return None
