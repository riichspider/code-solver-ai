# code-solver-ai — contexto para IA

## Estado atual
- 24 testes passando (100% pass rate)
- Python 3.10, Ollama local, Streamlit + CLI
- Health Score Revibe: ~75 (era 67 antes das melhorias)
- Fase 1, 2 e 3 do roadmap concluídas

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
- pre-commit configurado com ruff
- Roadmap público no README
- Release automático via GitHub Actions
- Templates de Issue e PR
- CHANGELOG.md e CONTRIBUTING.md
- Badges no README

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
- Testar pipeline com Ollama real no Streamlit
- Suporte a C++, Ruby, PHP (futuro)
- LRU eviction no cache (futuro)
- Plugin para VS Code (futuro)
- Suite de benchmarking (futuro)