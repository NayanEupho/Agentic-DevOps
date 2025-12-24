import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class AgenticSettings(BaseSettings):
    """
    Centralized configuration for DevOps Agent.
    Reads from environment variables, .env file, and defaults.
    """
    # LLM Configuration
    # LLM Configuration
    LLM_MODEL: str = "qwen2.5:72b-instruct"
    LLM_HOST: str = "http://10.20.39.12:11434"
    LLM_TEMPERATURE: float = 0.1
    LLM_FAST_MODEL: Optional[str] = "qwen2.5:72b-instruct" # Defaults to LLM_MODEL if not set
    LLM_FAST_HOST: Optional[str] = None # Defaults to LLM_HOST if not set
    
    # Embedding Model Configuration (Dedicated for speed)
    # Uses local Ollama by default for low-latency embeddings
    EMBEDDING_MODEL: str = "nomic-embed-text"  # Lightweight, fast embedding model
    EMBEDDING_HOST: str = "http://localhost:11434"  # Local Ollama for speed
    
    # Server Configuration
    MCP_SERVER_HOST: str = "127.0.0.1"
    
    # Ports (default to separate ports for isolation)
    DOCKER_PORT: int = 8080
    LOCAL_K8S_PORT: int = 8081
    REMOTE_K8S_PORT: int = 8082
    
    # Remote Kubernetes Configuration
    REMOTE_K8S_API_URL: str = "https://10.20.4.221:16443"
    REMOTE_K8S_TOKEN_PATH: str = "token.txt"
    REMOTE_K8S_VERIFY_SSL: bool = False
    
    # Timeouts
    CONTEXT_TIMEOUT: float = 5.0 # Seconds to wait for context injection
    
    # Safety
    SAFETY_CONFIRM: bool = True
    
    # Database
    DATABASE_NAME: str = "devops_agent.db"
    
    # Load from .env file if present
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        env_prefix="DEVOPS_",  # Variables must start with DEVOPS_, e.g., DEVOPS_LLM_MODEL
        extra='ignore'
    )

# Instantiate global settings object
settings = AgenticSettings()
