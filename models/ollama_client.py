from __future__ import annotations

import json
from typing import Any

import requests


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        default_model: str,
        timeout_seconds: int = 240,
        keep_alive: str = "10m",
        default_options: dict[str, Any] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds
        self.keep_alive = keep_alive
        self.default_options = default_options or {}
        self.session = requests.Session()

    def list_models(self) -> list[str]:
        try:
            response = self.session.get(f"{self.base_url}/tags", timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            raise OllamaError(
                f"Falha ao listar modelos do Ollama em {self.base_url}/tags. "
                "Verifique se o serviço está rodando."
            ) from exc

        if not response.ok:
            detail = self._extract_error_message(response)
            raise OllamaError(
                f"Ollama respondeu com erro ao listar modelos ({response.status_code}). {detail}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise OllamaError("Ollama retornou uma lista de modelos em formato inválido.") from exc

        return [item["name"] for item in payload.get("models", []) if item.get("name")]

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        options: dict[str, Any] | None = None,
        json_mode: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {**self.default_options, **(options or {})},
        }
        if json_mode:
            payload["format"] = "json"

        try:
            response = self.session.post(
            f"{self.base_url}/chat",
            json=payload,
            timeout=self.timeout_seconds,
        )
    except requests.RequestException as exc:
        raise OllamaError(
            "Falha ao conectar com o Ollama. Verifique se o serviço está rodando em "
            f"{self.base_url} e se o modelo foi baixado."
        ) from exc

    if not response.ok:
        detail = self._extract_error_message(response)
        if response.status_code == 404 and "model" in detail.lower() and "not found" in detail.lower():
            raise OllamaError(
                f"Modelo indisponível no Ollama: {detail}. "
                "Use `python main.py --list-models` para ver os modelos instalados."
            )
        raise OllamaError(f"Ollama respondeu com erro ({response.status_code}): {detail}")

    try:
        data = response.json()
    except ValueError as exc:
        raise OllamaError("Ollama retornou uma resposta inválida.") from exc

    if data.get("error"):
        raise OllamaError(f"Ollama retornou um erro: {data.get('error')}")
