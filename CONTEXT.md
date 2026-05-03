# code-solver-ai — contexto para IA

## Estado atual
- 24 testes passando (100% pass rate)
- Python 3.10, Ollama local, Streamlit + CLI
- Health Score Revibe: ~75 (era 67 antes das melhorias)

## O que já foi feito
- Pipeline completo: classify → reason → code → validate
- Auto-repair implementado
- Error handling consistente com mensagens amigáveis
- solve_batch centralizado em core/solver.py
- Test helpers dedicados em tests/test_helpers.py
- Cache TTL configurável via config.yaml (padrão 24h)
- Similaridade otimizada com Jaccard pre-filtering
- Testes multilanguage: TypeScript, Java, Go, Rust (6/6)
- Truncamentos silenciosos documentados com warnings
- README atualizado com exemplos de uso
- DeepSource integrado ao repositório (PRs #5 e #6 aceitos)
- CI com pytest no GitHub Actions (.github/workflows/ci.yml)
- Validação real para TypeScript (tsc) e Go (go test)
- Licença MIT adicionada (LICENSE)
- Health check CLI com --health-check
- Limpeza automática de exports (max 20 pastas)
- Python 3.10 declarado corretamente no pyproject.toml
- SECURITY.md reescrito para v0.1.0
- Dependabot configurado para pip

## Arquitetura
- core/solver.py — orquestrador principal
- core/classifier.py — classifica o problema
- core/reasoner.py — raciocina o plano
- core/coder.py — gera código e testes
- core/validator.py — executa e valida
- core/cache.py — cache JSON com TTL + histórico SQLite
- models/ollama_client.py — cliente Ollama
- utils/prompts.py — templates de prompt
- utils/executor.py — sandbox de execução
- app.py — Web UI Streamlit
- main.py — CLI

## Próximos passos pendentes
- Fase 2: badges no README
- Fase 2: criar CONTRIBUTING.md
- Fase 2: gravar screenshot/GIF do Streamlit
- Fase 2: criar CHANGELOG.md
- Fase 3: templates de Issue e PR
- Fase 3: configurar pre-commit com ruff
- Testar pipeline com Ollama real no Streamlit