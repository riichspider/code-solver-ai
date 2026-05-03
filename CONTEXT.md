# code-solver-ai — contexto para IA

## Estado atual
- 14 testes passando
- Python 3.10, Ollama local, Streamlit + CLI

## O que já foi feito
- Pipeline completo: classify → reason → code → validate
- Auto-repair implementado
- Error handling consistente
- solve_batch centralizado em core/solver.py
- Test helpers em tests/test_helpers.py
- Cache TTL configurável via config.yaml (padrão 24h)
- Similaridade otimizada com Jaccard pre-filtering

## Próximos passos pendentes
- Validar testes para TypeScript, Java, Go, Rust
- Atualizar README com exemplos de uso