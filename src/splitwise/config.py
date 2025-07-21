from dotenv import load_dotenv

load_dotenv()

AZURE_CONFIG = {
    "gpt-4o": {
        "endpoint_env": "AZURE_OPENAI_URL",
        "key_env": "AZURE_OPENAI_4O_API_KEY",
        "version_env": "AZURE_OPENAI_4O_API_VERSION",
        "default_version": "2024-12-01-preview",
        "deployment_name": "gpt-4o",
    },
}