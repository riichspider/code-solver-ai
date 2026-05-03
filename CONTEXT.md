# code-solver-ai — contexto para IA

## Estado atual
- 20 testes passando (100% pass rate)
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
- Rodar Health Check no Revibe para medir progresso real
- Testar pipeline funcionando com Ollama real no Streamlit
- Suporte a C++, Ruby, PHP (futuro)
- LRU eviction no cache (futuro)
- Suite de benchmarking (futuro)