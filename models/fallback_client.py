"""Fallback client with automatic model provider switching.

Priority order:
1. Ollama local (models/ollama_client.py)
2. Groq API (llama-3.3-70b-versatile)
3. Gemini API (gemini-2.0-flash)
"""

from __future__ import annotations

import json
import os
from typing import Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, user must set env vars manually

from models.ollama_client import OllamaClient, OllamaError
from utils.logger import get_logger


class GroqClient:
    """Groq API client implementation."""
    
    def __init__(self, api_key: str, timeout_seconds: int = 240):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.base_url = "https://api.groq.com/openai/v1"
        self.default_model = "llama-3.3-70b-versatile"
        self.logger = get_logger("groq_client")
        
        try:
            import requests
            self.session = requests.Session()
            self.session.headers.update({
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            })
        except ImportError:
            raise ImportError("requests is required for GroqClient")
    
    def list_models(self) -> list[str]:
        return [self.default_model]
    
    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        options: dict[str, Any] | None = None,
        json_mode: bool = False,
    ) -> dict[str, Any]:
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
            response.raise_for_status()
            
            data = response.json()
            message = data["choices"][0]["message"]
            
            return {
                "content": message["content"].strip(),
                "thinking": "",
                "raw": data,
            }
        except Exception as e:
            raise RuntimeError(f"Groq API error: {e}")
    
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
            raise RuntimeError(f"Groq returned invalid JSON: {e}")


class GeminiClient:
    """Gemini API client implementation."""
    
    def __init__(self, api_key: str, timeout_seconds: int = 240):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.default_model = "gemini-2.0-flash"
        self.logger = get_logger("gemini_client")
        
        try:
            import requests
            self.session = requests.Session()
        except ImportError:
            raise ImportError("requests is required for GeminiClient")
    
    def list_models(self) -> list[str]:
        return [self.default_model]
    
    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        options: dict[str, Any] | None = None,
        json_mode: bool = False,
    ) -> dict[str, Any]:
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
            response.raise_for_status()
            
            data = response.json()
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            
            return {
                "content": content.strip(),
                "thinking": "",
                "raw": data,
            }
        except Exception as e:
            raise RuntimeError(f"Gemini API error: {e}")
    
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
            raise RuntimeError(f"Gemini returned invalid JSON: {e}")


class FallbackClient:
    """Client with automatic fallback between providers."""
    
    def __init__(
        self,
        ollama_base_url: str = "http://localhost:11434/api",
        ollama_default_model: str = "qwen2.5-coder:latest",
        timeout_seconds: int = 240,
        keep_alive: str = "10m",
        default_options: dict[str, Any] | None = None,
    ) -> None:
        self.logger = get_logger("fallback_client")
        self.timeout_seconds = timeout_seconds
        
        # Initialize clients in priority order
        self.clients = []
        
        # 1. Ollama local
        try:
            self.clients.append({
                "name": "ollama",
                "client": OllamaClient(
                    base_url=ollama_base_url,
                    default_model=ollama_default_model,
                    timeout_seconds=timeout_seconds,
                    keep_alive=keep_alive,
                    default_options=default_options,
                ),
                "available": True,
            })
        except Exception as e:
            self.logger.warning(f"Failed to initialize Ollama client: {e}")
        
        # 2. Groq API
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            try:
                self.clients.append({
                    "name": "groq",
                    "client": GroqClient(groq_key, timeout_seconds),
                    "available": True,
                })
                self.logger.info("Groq client initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize Groq client: {e}")
        else:
            self.logger.info("GROQ_API_KEY not found, Groq disabled")
        
        # 3. Gemini API
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                self.clients.append({
                    "name": "gemini",
                    "client": GeminiClient(gemini_key, timeout_seconds),
                    "available": True,
                })
                self.logger.info("Gemini client initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize Gemini client: {e}")
        else:
            self.logger.info("GEMINI_API_KEY not found, Gemini disabled")
        
        if not self.clients:
            raise RuntimeError("No AI clients available. Check configuration.")
        
        self.current_client_index = 0
    
    def _get_available_client(self):
        """Get the next available client."""
        for i in range(len(self.clients)):
            client_info = self.clients[(self.current_client_index + i) % len(self.clients)]
            if client_info["available"]:
                self.current_client_index = (self.current_client_index + i) % len(self.clients)
                return client_info
        
        raise RuntimeError("No available AI clients")
    
    def _try_with_fallback(self, method_name: str, *args, **kwargs):
        """Try a method with fallback to next client."""
        last_error = None
        
        for attempt in range(len(self.clients)):
            try:
                client_info = self._get_available_client()
                client = client_info["client"]
                client_name = client_info["name"]
                
                self.logger.info(f"Using {client_name} client for {method_name}")
                
                method = getattr(client, method_name)
                result = method(*args, **kwargs)
                
                # Success - reset to primary client for next call
                self.current_client_index = 0
                self.logger.info(f"Successfully used {client_name} client")
                return result
                
            except (OllamaError, RuntimeError, Exception) as e:
                last_error = e
                client_info = self.clients[self.current_client_index]
                
                # Mark this client as unavailable for this call
                if isinstance(e, (OllamaError, RuntimeError)):
                    self.logger.warning(f"{client_info['name']} client failed: {e}")
                    self.current_client_index = (self.current_client_index + 1) % len(self.clients)
                else:
                    # For other exceptions, don't fallback
                    raise
        
        # All clients failed
        raise RuntimeError(f"All AI clients failed. Last error: {last_error}")
    
    def list_models(self) -> list[str]:
        """List available models from current client."""
        return self._try_with_fallback("list_models")
    
    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        options: dict[str, Any] | None = None,
        json_mode: bool = False,
    ) -> dict[str, Any]:
        """Generate text with automatic fallback."""
        return self._try_with_fallback(
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
        model: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate JSON with automatic fallback."""
        return self._try_with_fallback(
            "generate_json",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            options=options,
        )
