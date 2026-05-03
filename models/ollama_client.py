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
        response = self.session.get(f"{self.base_url}/tags", timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
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
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise OllamaError(
                "Falha ao conectar com o Ollama. Verifique se o serviço está rodando em "
                f"{self.base_url} e se o modelo foi baixado."
            ) from exc
        except ValueError as exc:
            raise OllamaError("Ollama retornou uma resposta inválida.") from exc

        if data.get("error"):
            raise OllamaError(str(data["error"]))

        message = data.get("message", {})
        return {
            "content": str(message.get("content", "")).strip(),
            "thinking": str(message.get("thinking", "")).strip(),
            "raw": data,
        }

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
        return self._parse_json(response["content"])

    def _parse_json(self, text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```") and cleaned.endswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1]).strip()

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise OllamaError("O modelo não retornou JSON estruturado.")
            payload = json.loads(cleaned[start : end + 1])

        if not isinstance(payload, dict):
            raise OllamaError("O modelo retornou JSON em formato inesperado.")
        return payload
