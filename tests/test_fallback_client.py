"""Test fallback client functionality."""

import os
import pytest
from unittest.mock import Mock, patch

from models.fallback_client import FallbackClient, GroqClient, GeminiClient
from models.ollama_client import OllamaError


class TestFallbackClient:
    """Test the fallback client implementation."""

    def setup_method(self):
        """Set up test environment."""
        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {
            'GROQ_API_KEY': 'test_groq_key',
            'GEMINI_API_KEY': 'test_gemini_key',
        })
        self.env_patcher.start()

    def teardown_method(self):
        """Clean up test environment."""
        self.env_patcher.stop()

    @patch('models.fallback_client.OllamaClient')
    @patch('models.fallback_client.GroqClient')
    @patch('models.fallback_client.GeminiClient')
    def test_client_initialization(self, mock_gemini, mock_groq, mock_ollama):
        """Test fallback client initialization."""
        # Mock successful client creation
        mock_ollama.return_value.list_models.return_value = ["test-model"]
        mock_groq.return_value.list_models.return_value = [
            "llama-3.3-70b-versatile"]
        mock_gemini.return_value.list_models.return_value = [
            "gemini-2.0-flash"]

        client = FallbackClient()

        # Should have 3 clients initialized
        assert len(client.clients) == 3
        assert client.clients[0]["name"] == "ollama"
        assert client.clients[1]["name"] == "groq"
        assert client.clients[2]["name"] == "gemini"

    @patch('models.fallback_client.OllamaClient')
    @patch('models.fallback_client.GroqClient')
    @patch('models.fallback_client.GeminiClient')
    def test_ollama_fallback_to_groq(self, mock_gemini, mock_groq, mock_ollama):
        """Test fallback from Ollama to Groq."""
        # Setup mocks
        mock_ollama_instance = Mock()
        mock_ollama_instance.generate_text.side_effect = OllamaError(
            "Ollama failed")
        mock_ollama.return_value = mock_ollama_instance

        mock_groq_instance = Mock()
        mock_groq_instance.generate_text.return_value = {
            "content": "Response from Groq",
            "thinking": "",
            "raw": {}
        }
        mock_groq.return_value = mock_groq_instance

        mock_gemini_instance = Mock()
        mock_gemini.return_value = mock_gemini_instance

        client = FallbackClient()

        # Should fallback to Groq
        result = client.generate_text(
            system_prompt="test",
            user_prompt="test"
        )

        assert result["content"] == "Response from Groq"
        mock_ollama_instance.generate_text.assert_called_once()
        mock_groq_instance.generate_text.assert_called_once()

    @patch('models.fallback_client.OllamaClient')
    def test_no_api_keys_warning(self, mock_ollama):
        """Test warning when API keys are missing."""
        # Remove API keys from environment
        with patch.dict(os.environ, {}, clear=True):
            mock_ollama.return_value.list_models.return_value = ["test-model"]

            with patch('models.fallback_client.get_logger') as mock_logger:
                client = FallbackClient()

                # Should only have Ollama client
                assert len(client.clients) == 1
                assert client.clients[0]["name"] == "ollama"

                # Should log warnings about missing keys
                mock_logger.return_value.info.assert_any_call(
                    "GROQ_API_KEY not found, Groq disabled")
                mock_logger.return_value.info.assert_any_call(
                    "GEMINI_API_KEY not found, Gemini disabled")

    @patch('models.fallback_client.OllamaClient')
    def test_no_clients_available_error(self, mock_ollama):
        """Test error when no clients are available."""
        # Make Ollama initialization fail
        mock_ollama.side_effect = Exception("Ollama init failed")

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="No AI clients available"):
                FallbackClient()


class TestGroqClient:
    """Test Groq client implementation."""

    @patch('requests.Session')
    def test_generate_text_success(self, mock_session_class):
        """Test successful text generation."""
        # Mock response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "Test response"
                }
            }]
        }

        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = GroqClient(api_key="test_key")
        result = client.generate_text(
            system_prompt="test system",
            user_prompt="test user"
        )

        assert result["content"] == "Test response"
        assert result["thinking"] == ""

    @patch('requests.Session')
    def test_generate_json_success(self, mock_session_class):
        """Test successful JSON generation."""
        # Mock response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"key": "value"}'
                }
            }]
        }

        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = GroqClient(api_key="test_key")
        result = client.generate_json(
            system_prompt="test system",
            user_prompt="test user"
        )

        assert result == {"key": "value"}


class TestGeminiClient:
    """Test Gemini client implementation."""

    @patch('requests.Session')
    def test_generate_text_success(self, mock_session_class):
        """Test successful text generation."""
        # Mock response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": "Test response"
                    }]
                }
            }]
        }

        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = GeminiClient(api_key="test_key")
        result = client.generate_text(
            system_prompt="test system",
            user_prompt="test user"
        )

        assert result["content"] == "Test response"
        assert result["thinking"] == ""

    @patch('requests.Session')
    def test_generate_json_success(self, mock_session_class):
        """Test successful JSON generation."""
        # Mock response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": '{"key": "value"}'
                    }]
                }
            }]
        }

        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = GeminiClient(api_key="test_key")
        result = client.generate_json(
            system_prompt="test system",
            user_prompt="test user"
        )

        assert result == {"key": "value"}
