from __future__ import annotations

from typing import Any

from utils.prompts import build_reasoning_user_prompt, reasoning_system_prompt


class ProblemReasoner:
    def __init__(self, client: Any) -> None:
        self.client = client

    def analyze(
        self,
        problem: str,
        classification: str,
        complexity: int,
        language: str,
        understanding: str,
        context_text: str,
        similar_context: list[dict[str, Any]],
        model: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        fallback = self._fallback(problem, classification, complexity, language, understanding)
        if self.client is None:
            return fallback

        try:
            payload = self.client.generate_json(
                system_prompt=reasoning_system_prompt(),
                user_prompt=build_reasoning_user_prompt(
                    problem=problem,
                    classification=classification,
                    complexity=complexity,
                    language=language,
                    understanding=understanding,
                    context_text=context_text,
                    similar_context=similar_context,
                ),
                model=model,
                options=options,
            )
        except Exception:
            return fallback

        plan_steps = payload.get("plan_steps") or fallback["plan_steps"]
        constraints = payload.get("constraints") or fallback["constraints"]
        risks = payload.get("risks") or fallback["risks"]
        success_criteria = payload.get("success_criteria") or fallback["success_criteria"]

        return {
            "understanding": str(payload.get("understanding", understanding)).strip() or fallback["understanding"],
            "plan_steps": self._clean_list(plan_steps, fallback["plan_steps"]),
            "constraints": self._clean_list(constraints, fallback["constraints"]),
            "risks": self._clean_list(risks, fallback["risks"]),
            "success_criteria": self._clean_list(success_criteria, fallback["success_criteria"]),
        }

    def _fallback(
        self,
        problem: str,
        classification: str,
        complexity: int,
        language: str,
        understanding: str,
    ) -> dict[str, Any]:
        return {
            "understanding": understanding,
            "plan_steps": [
                f"Entender a causa raiz do caso classificado como {classification}.",
                f"Projetar uma solução em {language} adequada à complexidade {complexity}/10.",
                "Gerar código limpo e direto ao ponto.",
                "Gerar testes cobrindo o fluxo principal e cenários de borda.",
                "Validar a execução de forma segura antes de formatar o relatório final.",
            ],
            "constraints": [
                "Manter a solução consistente com a linguagem escolhida.",
                "Evitar dependências externas desnecessárias.",
                "Priorizar clareza, correção e testabilidade.",
            ],
            "risks": [
                "Ambiguidade no problema original.",
                "Contexto incompleto pode exigir suposições mínimas.",
            ],
            "success_criteria": [
                "Código executável.",
                "Testes claros.",
                "Explicação objetiva.",
            ],
        }

    def _clean_list(self, value: Any, fallback: list[str]) -> list[str]:
        if not isinstance(value, list):
            return fallback
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or fallback
