import pytest

from models.ollama_client import OllamaClient, OllamaError


class FakeResponse:
    def __init__(self, status_code: int, json_payload=None, text: str = ""):
        self.status_code = status_code
        self._json_payload = json_payload
        self.text = text

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self):
        if self._json_payload is None:
            raise ValueError("invalid json")
        return self._json_payload


class FakeSession:
    def __init__(self, *, get_response=None, post_response=None):
        self.get_response = get_response
        self.post_response = post_response

    def get(self, *args, **kwargs):
        return self.get_response

    def post(self, *args, **kwargs):
        return self.post_response


def test_ollama_client_surfaces_missing_model_errors_clearly():
    client = OllamaClient(base_url="http://localhost:11434/api", default_model="fake-model")
    client.session = FakeSession(
        post_response=FakeResponse(
            404,
            json_payload={"error": "model 'missing-model' not found"},
        )
    )

    with pytest.raises(OllamaError, match="Modelo indisponível"):
        client.generate_json(
            system_prompt="Return JSON",
            user_prompt="{}",
            model="missing-model",
        )


def test_ollama_client_raises_clear_error_when_listing_models_fails():
    client = OllamaClient(base_url="http://localhost:11434/api", default_model="fake-model")
    client.session = FakeSession(
        get_response=FakeResponse(
            500,
            json_payload={"error": "internal server error"},
        )
    )

    with pytest.raises(OllamaError, match="listar modelos"):
        client.list_models()
