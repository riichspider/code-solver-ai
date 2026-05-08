"""Custom exceptions for different AI providers.

Defines specific exception types for better error handling and recovery strategies.
"""

from __future__ import annotations

from typing import Optional, Dict, Any
from enum import Enum


class ProviderType(Enum):
    """Supported AI providers."""
    OLLAMA = "ollama"
    GROQ = "groq"
    GEMINI = "gemini"


class ErrorType(Enum):
    """Types of errors that can occur."""
    RATE_LIMIT = "rate_limit"
    QUOTA_EXCEEDED = "quota_exceeded"
    CONNECTION_ERROR = "connection_error"
    TIMEOUT = "timeout"
    AUTHENTICATION = "authentication"
    MODEL_NOT_FOUND = "model_not_found"
    INVALID_REQUEST = "invalid_request"
    SERVER_ERROR = "server_error"
    CONTENT_FILTERED = "content_filtered"
    TOKEN_LIMIT = "token_limit"
    UNKNOWN = "unknown"


class BaseProviderException(Exception):
    """Base exception for all provider-specific errors."""
    
    def __init__(
        self,
        provider: ProviderType,
        message: str,
        error_type: ErrorType = ErrorType.UNKNOWN,
        status_code: Optional[int] = None,
        retry_after: Optional[int] = None,
        original_exception: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.error_type = error_type
        self.status_code = status_code
        self.retry_after = retry_after
        self.original_exception = original_exception
        self.context = context or {}
    
    def is_retryable(self) -> bool:
        """Check if this error is retryable."""
        retryable_types = {
            ErrorType.RATE_LIMIT,
            ErrorType.TIMEOUT,
            ErrorType.CONNECTION_ERROR,
            ErrorType.SERVER_ERROR,
        }
        return self.error_type in retryable_types
    
    def should_fallback(self) -> bool:
        """Check if we should fallback to another provider."""
        fallback_types = {
            ErrorType.RATE_LIMIT,
            ErrorType.QUOTA_EXCEEDED,
            ErrorType.CONNECTION_ERROR,
            ErrorType.SERVER_ERROR,
            ErrorType.MODEL_NOT_FOUND,
        }
        return self.error_type in fallback_types
    
    def get_backoff_seconds(self) -> int:
        """Get recommended backoff seconds for retry."""
        if self.error_type == ErrorType.RATE_LIMIT:
            return self.retry_after or 60
        elif self.error_type == ErrorType.TIMEOUT:
            return 30
        elif self.error_type == ErrorType.CONNECTION_ERROR:
            return 10
        elif self.error_type == ErrorType.SERVER_ERROR:
            return 15
        else:
            return 5


class RateLimitError(BaseProviderException):
    """Raised when rate limit is exceeded."""
    
    def __init__(
        self,
        provider: ProviderType,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        **kwargs
    ):
        super().__init__(
            provider=provider,
            message=message,
            error_type=ErrorType.RATE_LIMIT,
            retry_after=retry_after,
            **kwargs
        )


class QuotaExceededError(BaseProviderException):
    """Raised when quota is exceeded."""
    
    def __init__(
        self,
        provider: ProviderType,
        message: str = "Quota exceeded",
        **kwargs
    ):
        super().__init__(
            provider=provider,
            message=message,
            error_type=ErrorType.QUOTA_EXCEEDED,
            **kwargs
        )


class ConnectionError(BaseProviderException):
    """Raised when connection fails."""
    
    def __init__(
        self,
        provider: ProviderType,
        message: str = "Connection failed",
        **kwargs
    ):
        super().__init__(
            provider=provider,
            message=message,
            error_type=ErrorType.CONNECTION_ERROR,
            **kwargs
        )


class TimeoutError(BaseProviderException):
    """Raised when request times out."""
    
    def __init__(
        self,
        provider: ProviderType,
        message: str = "Request timeout",
        **kwargs
    ):
        super().__init__(
            provider=provider,
            message=message,
            error_type=ErrorType.TIMEOUT,
            **kwargs
        )


class AuthenticationError(BaseProviderException):
    """Raised when authentication fails."""
    
    def __init__(
        self,
        provider: ProviderType,
        message: str = "Authentication failed",
        **kwargs
    ):
        super().__init__(
            provider=provider,
            message=message,
            error_type=ErrorType.AUTHENTICATION,
            **kwargs
        )


class ModelNotFoundError(BaseProviderException):
    """Raised when requested model is not found."""
    
    def __init__(
        self,
        provider: ProviderType,
        model_name: str,
        message: Optional[str] = None,
        **kwargs
    ):
        if message is None:
            message = f"Model '{model_name}' not found"
        super().__init__(
            provider=provider,
            message=message,
            error_type=ErrorType.MODEL_NOT_FOUND,
            context={"model_name": model_name},
            **kwargs
        )


class InvalidRequestError(BaseProviderException):
    """Raised when request is invalid."""
    
    def __init__(
        self,
        provider: ProviderType,
        message: str = "Invalid request",
        **kwargs
    ):
        super().__init__(
            provider=provider,
            message=message,
            error_type=ErrorType.INVALID_REQUEST,
            **kwargs
        )


class ServerError(BaseProviderException):
    """Raised when server error occurs."""
    
    def __init__(
        self,
        provider: ProviderType,
        message: str = "Server error",
        **kwargs
    ):
        super().__init__(
            provider=provider,
            message=message,
            error_type=ErrorType.SERVER_ERROR,
            **kwargs
        )


class ContentFilteredError(BaseProviderException):
    """Raised when content is filtered."""
    
    def __init__(
        self,
        provider: ProviderType,
        message: str = "Content filtered",
        **kwargs
    ):
        super().__init__(
            provider=provider,
            message=message,
            error_type=ErrorType.CONTENT_FILTERED,
            **kwargs
        )


class TokenLimitError(BaseProviderException):
    """Raised when token limit is exceeded."""
    
    def __init__(
        self,
        provider: ProviderType,
        message: str = "Token limit exceeded",
        **kwargs
    ):
        super().__init__(
            provider=provider,
            message=message,
            error_type=ErrorType.TOKEN_LIMIT,
            **kwargs
        )


def parse_provider_error(
    provider: ProviderType,
    exception: Exception,
    status_code: Optional[int] = None,
    response_text: Optional[str] = None
) -> BaseProviderException:
    """Parse generic exception into specific provider exception."""
    
    # Parse based on status code
    if status_code:
        if status_code == 429:
            return RateLimitError(provider, original_exception=exception, status_code=status_code)
        elif status_code == 401:
            return AuthenticationError(provider, original_exception=exception, status_code=status_code)
        elif status_code == 404:
            return ModelNotFoundError(provider, "unknown", original_exception=exception, status_code=status_code)
        elif status_code == 400:
            return InvalidRequestError(provider, original_exception=exception, status_code=status_code)
        elif status_code >= 500:
            return ServerError(provider, original_exception=exception, status_code=status_code)
    
    # Parse based on exception message
    error_message = str(exception).lower()
    
    if "rate limit" in error_message or "too many requests" in error_message:
        return RateLimitError(provider, str(exception), original_exception=exception)
    elif "quota" in error_message or "billing" in error_message:
        return QuotaExceededError(provider, str(exception), original_exception=exception)
    elif "timeout" in error_message or "timed out" in error_message:
        return TimeoutError(provider, str(exception), original_exception=exception)
    elif "connection" in error_message or "network" in error_message:
        return ConnectionError(provider, str(exception), original_exception=exception)
    elif "auth" in error_message or "unauthorized" in error_message:
        return AuthenticationError(provider, str(exception), original_exception=exception)
    elif "model" in error_message and "not found" in error_message:
        return ModelNotFoundError(provider, "unknown", str(exception), original_exception=exception)
    elif "token" in error_message and ("limit" in error_message or "exceed" in error_message):
        return TokenLimitError(provider, str(exception), original_exception=exception)
    elif "content" in error_message and ("filter" in error_message or "policy" in error_message):
        return ContentFilteredError(provider, str(exception), original_exception=exception)
    else:
        return BaseProviderException(
            provider=provider,
            message=str(exception),
            error_type=ErrorType.UNKNOWN,
            original_exception=exception,
            status_code=status_code
        )


class ExceptionHandler:
    """Handler for managing provider exceptions with retry logic."""
    
    def __init__(self, max_retries: int = 3, base_backoff: int = 1):
        self.max_retries = max_retries
        self.base_backoff = base_backoff
    
    def handle_with_retry(
        self,
        func,
        provider: ProviderType,
        *args,
        **kwargs
    ):
        """Execute function with retry logic for retryable exceptions."""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except BaseProviderException as e:
                last_exception = e
                
                if not e.is_retryable() or attempt >= self.max_retries:
                    raise
                
                backoff = e.get_backoff_seconds() * (2 ** attempt)  # Exponential backoff
                import time
                time.sleep(backoff)
                
            except Exception as e:
                # Convert to provider exception
                provider_exception = parse_provider_error(provider, e)
                last_exception = provider_exception
                
                if not provider_exception.is_retryable() or attempt >= self.max_retries:
                    raise provider_exception
                
                backoff = provider_exception.get_backoff_seconds() * (2 ** attempt)
                import time
                time.sleep(backoff)
        
        raise last_exception
