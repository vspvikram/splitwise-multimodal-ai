import os
from enum import Enum
from typing import Dict, Tuple
from loguru import logger
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from src.splitwise.config import AZURE_CONFIG

load_dotenv()


class LLMProviderType(Enum):
    AZURE_OPENAI = "azure_openai"

_client_cache: Dict[str, OpenAIProvider] = {} # cache for Azure OpenAI clients
_model_cache: Dict[str, OpenAIModel] = {} # cache for LLM models

def _get_azure_client(
        endpoint: str, api_key: str,
        api_version: str
) -> AsyncAzureOpenAI:
    """Creates or retrieves a chached AsyncAzureOpenAI client."""

    client_key = f"{endpoint}:{api_version}"
    if client_key not in _client_cache:
        logger.info(f"Creating new AsyncAzureOpenAI client for endpoint: {endpoint}")
        if not endpoint or not api_key:
            raise ValueError("Endpoint or API key are missing, both must be provided.")
        
        try:
            _client_cache[client_key] = AsyncAzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version=api_version,
            )
        except Exception as e:
            logger.error(f"Failed to create AsyncAzureOpenAI client: {e}")
            raise
    else:
        logger.info(f"Using cached AsyncAzureOpenAI client for endpoint: {endpoint}")
    return _client_cache[client_key]

def get_model(
        model_name: str,
        provider_type: LLMProviderType = LLMProviderType.AZURE_OPENAI,
        **kwargs,
) -> OpenAIModel:
    """Retrieves a model based on the provided model name and provider type.
    
    Args:
        model_name (str): Logical name or deployment name of the model to retrieve. Must match a key in the AZURE_CONFIG
        provider_type (LLMProviderType): The type of LLM provider (instance of LLMProviderType).
        **kwargs: Additional arguments for the model."""
    
    if not isinstance(provider_type, LLMProviderType):
        raise ValueError("provider_type must be an instance of LLMProviderType.")
    
    cache_key = f"{provider_type.value}:{model_name}"
    if cache_key in _model_cache:
        logger.info(f"Using cached model for {cache_key}")
        return _model_cache[cache_key]
    
    logger.info(f"Creating new model instance for key: {cache_key}")

    # provider specific logic
    if provider_type == LLMProviderType.AZURE_OPENAI:
        if model_name not in AZURE_CONFIG:
            raise ValueError(f"Model {model_name} not found in AZURE_CONFIG.")
        config = AZURE_CONFIG[model_name]
        endpoint = os.getenv(config["endpoint_env"])
        api_key = os.getenv(config["key_env"])
        api_version = os.getenv(config["version_env"], config["default_version"])
        deployment_name = config["deployment_name"]

        if not endpoint or not api_key:
            raise ValueError("Endpoint or API key are missing, both must be provided.")
        
        client = _get_azure_client(endpoint=endpoint, api_key=api_key, api_version=api_version)

        provider_instance = OpenAIProvider(openai_client=client)

        model_instance = OpenAIModel(
            deployment_name, provider=provider_instance, **kwargs
        )

        _model_cache[cache_key] = model_instance
        logger.info(f"Successfully created and cached model instance for {cache_key}")
        return model_instance
    
    else:
        raise ValueError(f"Unsupported provider type: {provider_type}.")
    

# Pre-initialization function ---
def initialize_models(models_to_init: list[Tuple[str, LLMProviderType]]):
    """
    Optional function to pre-initialzie specific models."""
    
    logger.info("Pre-initializing specific LLM models...")
    for model_name, provider_type in models_to_init:
        try:
            get_model(model_name, provider_type)
            logger.info(f"Successfully pre-initialized model: {model_name} with provider: {provider_type}")
        except Exception as e:
            logger.error(f"Failed to pre-initialize model {model_name}: {e}")
    logger.info("Pre-initialization of LLM models completed.")