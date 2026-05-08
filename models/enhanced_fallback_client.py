"""Enhanced fallback client with specific exception handling.

Implements provider-specific error handling, retry logic, and intelligent fallback
strategies with detailed error reporting and recovery mechanisms.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from models.ollama_client import OllamaClient, OllamaError
from utils.exceptions import (
    ProviderType, ErrorType, BaseProviderException, parse_provider_error,
    ExceptionHandler
)
from utils.logger import get_logger


@dataclass
class ProviderStats:
    """Statistics for a specific provider."""
    name: str
    success_count: int = 0
    failure_count: int = 0
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    consecutive_failures: int = 0
    is_healthy: bool = True
    error_types: Dict[str, int] = None
    
    def __post_init__(self):
        if self.error_types is None:
            self.error_types = {}
    
    def record_success(self):
        """Record a successful request."""
        self.success_count += 1
        self.last_success = time.time()
        self.consecutive_failures = 0
        self.is_healthy = True
    
    def record_failure(self, error: BaseProviderException):
        """Record a failed request."""
        self.failure_count += 1
        self.last_failure = time.time()
        self.consecutive_failures += 1
        
        # Mark as unhealthy after multiple consecutive failures
        if self.consecutive_failures >= 3:
            self.is_healthy = False
        
        # Track error types
        error_type = error.error_type.value
        self.error_types[error_type] = self.error_types.get(error_type, 0) + 1
    
    def get_success_rate(self) -> float:
        """Get success rate (0.0 to 1.0)."""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0
    
    def should_attempt(self) -> bool:
        """Check if provider should be attempted."""
        # Don't attempt if marked unhealthy and has recent failures
        if not self.is_healthy and self.consecutive_failures > 0:
            # Allow retry after backoff period
            if self.last_failure and (time.time() - self.last_failure) < 300:  # 5 minutes
                return False
        return True


class EnhancedGroqClient:
    """Enhanced Groq client with specific error handling."""
    
    def __init__(self, api_key: str, timeout_seconds: int = 240):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.base_url = "https://api.groq.com/openai/v1"
        self.default_model = "llama-3.3-70b-versatile"
        self.logger = get_logger("enhanced_groq_client")
        self.exception_handler = ExceptionHandler(max_retries=2, base_backoff=1)
        
        try:
            import requests
            self.session = requests.Session()
            self.session.headers.update({
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            })
        except ImportError:
            raise ImportError("requests is required for EnhancedGroqClient")
    
    def list_models(self) -> List[str]:
        return [self.default_model]
    
    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        json_mode: bool = False,
    ) -> Dict[str, Any]:
        """Generate text with enhanced error handling."""
        
        def _generate():
            payload = {
                "model": model or self.default_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
            }
            
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            
            try:
                response = self.session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    timeout=self.timeout_seconds,
                )
                
                if response.status_code == 429:
                    retry_after = int(response.headers.get('retry-after', 60))
                    raise parse_provider_error(
                        ProviderType.GROQ,
                        Exception(f"Rate limit exceeded. Retry after {retry_after}s"),
                        status_code=429,
                        response_text=response.text
                    )
                elif response.status_code == 401:
                    raise parse_provider_error(
                        ProviderType.GROQ,
                        Exception("Invalid API key"),
                        status_code=401
                    )
                elif response.status_code == 404:
                    raise parse_provider_error(
                        ProviderType.GROQ,
                        Exception(f"Model {model or self.default_model} not found"),
                        status_code=404
                    )
                elif response.status_code >= 500:
                    raise parse_provider_error(
                        ProviderType.GROQ,
                        Exception(f"Server error: {response.status_code}"),
                        status_code=response.status_code
                    )
                
                response.raise_for_status()
                
                data = response.json()
                message = data["choices"][0]["message"]
                
                return {
                    "content": message["content"].strip(),
                    "thinking": "",
                    "raw": data,
                }
                
            except Exception as e:
                if isinstance(e, BaseProviderException):
                    raise
                raise parse_provider_error(
                    ProviderType.GROQ,
                    e,
                    response_text=getattr(response, 'text', None)
                )
        
        return self.exception_handler.handle_with_retry(_generate, ProviderType.GROQ)
    
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate JSON with enhanced error handling."""
        response = self.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            options=options,
            json_mode=True,
        )
        
        try:
            return json.loads(response["content"])
        except json.JSONDecodeError as e:
            raise parse_provider_error(
                ProviderType.GROQ,
                Exception(f"Invalid JSON response: {e}")
            )


class EnhancedGeminiClient:
    """Enhanced Gemini client with specific error handling."""
    
    def __init__(self, api_key: str, timeout_seconds: int = 240):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.default_model = "gemini-2.0-flash"
        self.logger = get_logger("enhanced_gemini_client")
        self.exception_handler = ExceptionHandler(max_retries=2, base_backoff=1)
        
        try:
            import requests
            self.session = requests.Session()
        except ImportError:
            raise ImportError("requests is required for EnhancedGeminiClient")
    
    def list_models(self) -> List[str]:
        return [self.default_model]
    
    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        json_mode: bool = False,
    ) -> Dict[str, Any]:
        """Generate text with enhanced error handling."""
        
        def _generate():
            model_name = model or self.default_model
            
            # Gemini combines system and user prompts
            combined_prompt = f"System: {system_prompt}\n\nUser: {user_prompt}"
            
            payload = {
                "contents": [{"parts": [{"text": combined_prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                }
            }
            
            if json_mode:
                payload["generationConfig"]["responseMimeType"] = "application/json"
            
            try:
                response = self.session.post(
                    f"{self.base_url}/models/{model_name}:generateContent",
                    json=payload,
                    params={"key": self.api_key},
                    timeout=self.timeout_seconds,
                )
                
                if response.status_code == 429:
                    raise parse_provider_error(
                        ProviderType.GEMINI,
                        Exception("Rate limit exceeded"),
                        status_code=429
                    )
                elif response.status_code == 400:
                    error_data = response.json()
                    if "quota" in str(error_data).lower():
                        raise parse_provider_error(
                            ProviderType.GEMINI,
                            Exception("Quota exceeded"),
                            status_code=400
                        )
                    raise parse_provider_error(
                        ProviderType.GEMINI,
                        Exception(f"Invalid request: {error_data}"),
                        status_code=400
                    )
                elif response.status_code >= 500:
                    raise parse_provider_error(
                        ProviderType.GEMINI,
                        Exception(f"Server error: {response.status_code}"),
                        status_code=response.status_code
                    )
                
                response.raise_for_status()
                
                data = response.json()
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                
                return {
                    "content": content.strip(),
                    "thinking": "",
                    "raw": data,
                }
                
            except Exception as e:
                if isinstance(e, BaseProviderException):
                    raise
                raise parse_provider_error(
                    ProviderType.GEMINI,
                    e,
                    response_text=getattr(response, 'text', None)
                )
        
        return self.exception_handler.handle_with_retry(_generate, ProviderType.GEMINI)
    
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate JSON with enhanced error handling."""
        response = self.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            options=options,
            json_mode=True,
        )
        
        try:
            return json.loads(response["content"])
        except json.JSONDecodeError as e:
            raise parse_provider_error(
                ProviderType.GEMINI,
                Exception(f"Invalid JSON response: {e}")
            )


class EnhancedFallbackClient:
    """Enhanced fallback client with intelligent error handling."""
    
    def __init__(
        self,
        ollama_base_url: str = "http://localhost:11434/api",
        ollama_default_model: str = "qwen2.5-coder:latest",
        timeout_seconds: int = 240,
        keep_alive: str = "10m",
        default_options: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.logger = get_logger("enhanced_fallback_client")
        self.timeout_seconds = timeout_seconds
        
        # Initialize provider statistics
        self.provider_stats: Dict[str, ProviderStats] = {}
        
        # Initialize clients in priority order
        self.clients = []
        
        # 1. Ollama local
        try:
            ollama_client = OllamaClient(
                base_url=ollama_base_url,
                default_model=ollama_default_model,
                timeout_seconds=timeout_seconds,
                keep_alive=keep_alive,
                default_options=default_options,
            )
            self.clients.append({
                "name": "ollama",
                "provider": ProviderType.OLLAMA,
                "client": ollama_client,
                "available": True,
            })
            self.provider_stats["ollama"] = ProviderStats("ollama")
        except Exception as e:
            self.logger.warning(f"Failed to initialize Ollama client: {e}")
            self.provider_stats["ollama"] = ProviderStats("ollama")
            self.provider_stats["ollama"].record_failure(
                parse_provider_error(ProviderType.OLLAMA, e)
            )
        
        # 2. Groq API
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            try:
                groq_client = EnhancedGroqClient(groq_key, timeout_seconds)
                self.clients.append({
                    "name": "groq",
                    "provider": ProviderType.GROQ,
                    "client": groq_client,
                    "available": True,
                })
                self.provider_stats["groq"] = ProviderStats("groq")
                self.logger.info("Enhanced Groq client initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize Groq client: {e}")
                self.provider_stats["groq"] = ProviderStats("groq")
                self.provider_stats["groq"].record_failure(
                    parse_provider_error(ProviderType.GROQ, e)
                )
        else:
            self.logger.info("GROQ_API_KEY not found, Groq disabled")
            self.provider_stats["groq"] = ProviderStats("groq")
        
        # 3. Gemini API
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                gemini_client = EnhancedGeminiClient(gemini_key, timeout_seconds)
                self.clients.append({
                    "name": "gemini",
                    "provider": ProviderType.GEMINI,
                    "client": gemini_client,
                    "available": True,
                })
                self.provider_stats["gemini"] = ProviderStats("gemini")
                self.logger.info("Enhanced Gemini client initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize Gemini client: {e}")
                self.provider_stats["gemini"] = ProviderStats("gemini")
                self.provider_stats["gemini"].record_failure(
                    parse_provider_error(ProviderType.GEMINI, e)
                )
        else:
            self.logger.info("GEMINI_API_KEY not found, Gemini disabled")
            self.provider_stats["gemini"] = ProviderStats("gemini")
        
        if not self.clients:
            raise RuntimeError("No AI clients available. Check configuration.")
        
        self.current_client_index = 0
    
    def _get_next_available_client(self) -> Optional[Dict[str, Any]]:
        """Get the next available healthy client."""
        available_clients = []
        
        for client_info in self.clients:
            stats = self.provider_stats[client_info["name"]]
            if client_info["available"] and stats.should_attempt():
                available_clients.append(client_info)
        
        if not available_clients:
            return None
        
        # Sort by success rate and consecutive failures
        available_clients.sort(
            key=lambda x: (
                self.provider_stats[x["name"]].get_success_rate(),
                -self.provider_stats[x["name"]].consecutive_failures
            ),
            reverse=True
        )
        
        return available_clients[0]
    
    def _try_with_intelligent_fallback(self, method_name: str, *args, **kwargs):
        """Try method with intelligent fallback and error tracking."""
        last_error = None
        attempted_providers = []
        
        for attempt in range(len(self.clients)):
            client_info = self._get_next_available_client()
            
            if not client_info:
                self.logger.error("No healthy providers available")
                break
            
            if client_info["name"] in attempted_providers:
                continue  # Don't retry same provider
            
            attempted_providers.append(client_info["name"])
            client = client_info["client"]
            provider = client_info["provider"]
            provider_name = client_info["name"]
            
            try:
                self.logger.info(f"Attempting {provider_name} for {method_name}")
                
                method = getattr(client, method_name)
                result = method(*args, **kwargs)
                
                # Record success
                self.provider_stats[provider_name].record_success()
                
                self.logger.info(f"Successfully used {provider_name} for {method_name}")
                return result
                
            except BaseProviderException as e:
                last_error = e
                self.provider_stats[provider_name].record_failure(e)
                
                self.logger.warning(
                    f"{provider_name} failed for {method_name}: "
                    f"{e.error_type.value} - {str(e)[:100]}"
                )
                
                # Don't fallback for non-fallbackable errors
                if not e.should_fallback():
                    self.logger.error(f"Non-fallbackable error from {provider_name}: {e}")
                    raise
                
                # Mark client as temporarily unavailable for certain errors
                if e.error_type in [ErrorType.RATE_LIMIT, ErrorType.QUOTA_EXCEEDED]:
                    client_info["available"] = False
                    
            except Exception as e:
                # Convert to provider exception
                provider_exception = parse_provider_error(provider, e)
                last_error = provider_exception
                self.provider_stats[provider_name].record_failure(provider_exception)
                
                self.logger.warning(
                    f"Unexpected error from {provider_name}: {str(e)[:100]}"
                )
        
        # All clients failed
        if last_error:
            self.logger.error(f"All providers failed. Last error: {last_error}")
            raise last_error
        else:
            raise RuntimeError("No providers available")
    
    def list_models(self) -> List[str]:
        """List available models from current client."""
        return self._try_with_intelligent_fallback("list_models")
    
    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        json_mode: bool = False,
    ) -> Dict[str, Any]:
        """Generate text with intelligent fallback."""
        return self._try_with_intelligent_fallback(
            "generate_text",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            options=options,
            json_mode=json_mode,
        )
    
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate JSON with intelligent fallback."""
        return self._try_with_intelligent_fallback(
            "generate_json",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            options=options,
        )
    
    def get_provider_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all providers."""
        return {
            name: {
                "success_count": stats.success_count,
                "failure_count": stats.failure_count,
                "success_rate": stats.get_success_rate(),
                "consecutive_failures": stats.consecutive_failures,
                "is_healthy": stats.is_healthy,
                "last_success": stats.last_success,
                "last_failure": stats.last_failure,
                "error_types": stats.error_types,
            }
            for name, stats in self.provider_stats.items()
        }
    
    def reset_provider_stats(self, provider_name: Optional[str] = None):
        """Reset statistics for a specific provider or all providers."""
        if provider_name:
            if provider_name in self.provider_stats:
                self.provider_stats[provider_name] = ProviderStats(provider_name)
        else:
            for name in self.provider_stats:
                self.provider_stats[name] = ProviderStats(name)
