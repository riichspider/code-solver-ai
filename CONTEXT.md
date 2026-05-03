# code-solver-ai — contexto para IA

## Estado atual
- 14 testes passando
- Health Score Revibe: ~75 (melhorado de 67)
- Python 3.10, Ollama local, Streamlit + CLI

## O que já foi feito
- Pipeline completo: classify → reason → code → validate
- Auto-repair implementado
- Error handling consistente
- solve_batch centralizado em core/solver.py
- Test helpers em tests/test_helpers.py

## Problemas conhecidos
- config.yaml aponta para modelo não instalado (qwen2.5-coder:7b)
- Similaridade do histórico escala mal acima de 500 entradas

## Próximos passos pendentes
- Validar testes para TypeScript, Java, Go, Rust
- TTL no cache