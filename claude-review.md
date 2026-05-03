## Avaliação técnica — `code-solver-ai`

Leitura completa de todos os 18 arquivos-fonte, 3 arquivos de teste, exports, cache e histórico. Aqui vai o diagnóstico sem filtro.

---

### 1. Visão geral do estado do projeto

O projeto está em **MVP técnico funcional**. Não é mais um protótipo descartável — tem estrutura intencional, pipeline modular, persistência real, UI dupla (CLI + Streamlit) e testes automatizados com fake client. Ao mesmo tempo, está longe de ser produção: a resiliência do pipeline ainda depende muito da qualidade do modelo, a cobertura de testes cobre apenas o caminho feliz, e há dívida técnica concentrada em partes críticas.

**Nota de maturidade: 5/10.** Base promissora com fundação razoável, mas ainda frágil em produção real.

---

### 2. O que está bom

**Arquitetura geral (`core/solver.py`):** O `CodeSolver` faz bem o papel de orquestrador. Recebe um `SolveRequest`, distribui para as etapas, lida com cache, histórico e exportação. A separação de responsabilidades é real — cada módulo em `core/` tem uma única responsabilidade bem definida. Isso não é trivial para um projeto nesse estágio.

**Fallback e resiliência do classificador/reasoner:** Tanto `classifier.py` quanto `reasoner.py` têm fallbacks locais que não dependem do modelo. Se o LLM falhar ou retornar lixo, o pipeline continua. Essa decisão foi boa e está implementada com cuidado.

**`OllamaClient` (`models/ollama_client.py`):** Código limpo. Usa `requests.Session`, trata erros HTTP, trata falha de parse JSON com extração de substring (`{...}`), e distingue erro de rede de erro de conteúdo. É o módulo mais sólido do projeto.

**Cache com hash determinístico (`core/cache.py`):** `build_key` normaliza texto antes de gerar o SHA-256. Cache por arquivo JSON é simples e funciona bem para esse volume. `HistoryStore` usa SQLite corretamente com índices e similaridade por `SequenceMatcher` + Jaccard — uma solução razoável sem dependências de embedding.

**Sistema de prompts (`utils/prompts.py`):** Os prompts têm estrutura clara: system separado do user, schema JSON explícito em cada prompt, exemplo few-shot no prompt de coding. A instrução de barrar `chai/jest/mocha/vitest` para JavaScript está no lugar certo.

**`SandboxExecutor` (`utils/executor.py`):** Usa `subprocess.run` com `shell=False`, `capture_output=True` e `timeout`. Simples e correto. Protege contra timeout e não usa `shell=True`.

**`test_solver.py`:** O `FakeOllamaClient` com respostas pré-gravadas por índice de chamada é uma boa decisão de design para testes unitários. Cobre pipeline completo, cache e fallback de modelo. São os testes mais valiosos do repositório.

---

### 3. O que está ruim ou frágil

**`config.yaml` ainda aponta para `qwen2.5-coder:7b` como `default_model`** — o mesmo modelo que causou falha e foi identificado como não instalado. O fallback funciona, mas a config está errada desde o primeiro commit. Todo novo usuário vai tropeçar nesse comportamento. Isso deveria ser corrigido ou o campo deveria ser obrigatório via validação no `from_config`.

**`_resolve_model` chama `list_models()` implicitamente na primeira resolução, mas erros silenciosos retornam `[]`** (`core/solver.py`, linha do `except Exception`). Isso significa que se o Ollama estiver fora do ar, o modelo resolvido vai ser `self.default_model` — que pode não existir. O pipeline vai falhar mais tarde com uma mensagem de erro confusa do Ollama, não com um erro claro de "modelo não disponível".

**`coder.py` lança `RuntimeError` genérico se o código vier vazio.** O problema é que esse `RuntimeError` sobe direto para o `solver.py` sem captura — o pipeline inteiro quebra em vez de tentar o auto-repair. A lógica de repair só é acionada quando `validation.status == "failed"`, mas a geração pode falhar antes da validação.

**`_strip_code_fences` em `coder.py` é frágil.** Só remove fences se o texto começa com ` ``` ` E termina com ` ``` `. Qualquer variação (espaço antes, newline extra, fence dupla) e o código vai incluir a marcação literal no arquivo gerado. No teste de JavaScript com modelo pequeno, isso foi a causa do `\n` literal dentro do código.

**`parse_batch_text` em `solver.py` tem heurística instável.** A lógica de separação por `\n---\n`, depois por parágrafo duplo, depois por linhas individuais é frágil e não testada. Um arquivo batch com bullets misturados com parágrafos vai ser parseado incorretamente sem qualquer aviso.

**Ausência de type hints nos construtores dos módulos de core.** `ProblemClassifier.__init__`, `ProblemReasoner.__init__` e `CodeGenerator.__init__` aceitam `client` sem tipo declarado. Isso não causa bug direto, mas dificulta qualquer tooling e impede `mypy` de ser útil.

**`app.py` captura qualquer exceção com `st.error(str(exc))`** — isso expõe stack traces de implementação ao usuário final se um erro interno acontecer. Para produção, é um problema de UX e segurança leve.

**`__pycache__` e `db/history.db` estão presentes no ZIP.** Isso indica que o `.gitignore` não está coberto corretamente no estado atual do workspace local, mesmo que o git esteja limpo.

---

### 4. Falhas já encontradas e sua leitura

| Falha original | Fix feito | Qualidade do fix | O que ficou pendente |
|---|---|---|---|
| `default_model` apontando para modelo não instalado | Fallback automático em `_resolve_model` | Bom | `config.yaml` ainda tem o modelo errado; nenhuma validação em `from_config` |
| pytest capturando exports | `testpaths = ["tests"]` no `pyproject.toml` | Correto e definitivo | Nada |
| `history.db` versionado | `db/.gitkeep` + `.gitignore` | Correto | Cache JSON em `db/cache/` ainda está versionado no ZIP (5 arquivos) |
| Estrutura aninhada do repo | Flatten para root | Correto | Sobrou pasta `code-solver-ai/` vazia no workspace |
| JS usando `chai`/dependências externas | Instrução no `coding_system_prompt` | Bom, mas não definitivo | Modelos pequenos ainda ignoram a instrução; sem fallback de retry específico para esse erro |

O fix do `default_model` é o mais importante e está bem feito. O fix de JS é paliativo — a instrução no prompt ajuda modelos maiores, mas não resolve o problema nos menores, que é estrutural.

---

### 5. Riscos técnicos

**Risco alto — Confiabilidade dependente do modelo:** O pipeline assume que o LLM vai retornar JSON estruturado sempre. Quando não retorna (modelos pequenos), o fallback do classifier/reasoner funciona, mas o `coder` lança exceção. Se o modelo retornar código sintaticamente válido mas logicamente errado, o auto-repair tem uma chance, mas sem garantia. Isso é intrínseco ao problema, mas o projeto não tem circuit breaker.

**Risco médio — Cache sem TTL e sem invalidação:** `SolverCache` é eterno. Se o mesmo problema for resolvido com dois modelos diferentes, o cache vai depender da ordem. Mais grave: não há como expirar entradas antigas ou limpar o cache por chave seletivamente.

**Risco médio — Similaridade por `SequenceMatcher` escala mal:** `find_similar` busca os últimos 50 registros e faz comparação O(N) de strings. Para um histórico com centenas de entradas, isso vai ficar lento. Sem FTS ou embedding, não há atalho além de limitar o `candidate_pool`.

**Risco baixo-médio — Python 3.10 vs 3.11 declarado:** `pyproject.toml` declara `requires-python = ">=3.11"`, mas o ambiente está em 3.10 e tudo funciona. Isso vai causar problemas se alguém adicionar sintaxe 3.11-específica (ex: `tomllib`, `match` com pattern avançado). A discrepância deveria ser resolvida.

**Risco baixo — `export_result` gera diretórios com timestamp:** Dois exports do mesmo problema com menos de 1 segundo de diferença vão gerar pastas diferentes. Para batch longo, o diretório `exports/` vai crescer ilimitadamente sem limpeza.

---

### 6. Próximos passos priorizados

**Crítico**

- Corrigir `config.yaml` para apontar para um modelo que realmente existe no ambiente, ou adicionar validação em `from_config` que avise quando o `default_model` não está instalado
- Adicionar captura de `RuntimeError` no `solver.solve()` para o caso de `coder.generate()` falhar, com mensagem clara ao usuário
- Melhorar `_strip_code_fences` para ser mais tolerante (regex, não startswith/endswith simples)

**Importante**

- Adicionar pelo menos um teste de integração end-to-end com mock de `requests` para simular resposta do Ollama sem serviço real — isso cobre o caminho de falha de rede
- Adicionar testes para `parse_batch_text` com casos de edge: arquivo vazio, um item, bullets, separador `---`, parágrafo único
- Adicionar TTL básico ao `SolverCache` (timestamp no JSON + verificação na leitura)
- Type hints nos construtores de `core/`
- Adicionar `mypy` ao CI local (mesmo que informal)

**Desejável**

- Resolver a discrepância Python 3.10 vs 3.11 (declarar 3.10 no `pyproject.toml` ou migrar o ambiente)
- Limitar crescimento de `exports/` com opção de cleanup ou diretório por data
- Logging estruturado mínimo (ao invés de `rich` puro no CLI, um `logging.getLogger` nos módulos core facilita debug)
- Adicionar um teste de comportamento ruim do modelo: quando `generate_json` retorna payload sem `code`, verificar que a exceção é capturada com mensagem útil
- Remover `__pycache__` e `db/cache/*.json` do workspace rastreado

---

### 7. Veredito final

O projeto está andando bem para o estágio atual. O pipeline de 4 etapas (classify → reason → code → validate) está implementado com separação real de responsabilidades, não é código de script colado em funções. O `FakeOllamaClient` nos testes mostra maturidade de design — você consegue testar o pipeline inteiro sem Ollama real.

O que o separa de "base sólida" para "MVP confiável" são principalmente três coisas: melhor resiliência no `coder.py` quando o modelo retorna lixo, testes cobrindo os caminhos de falha (não só o caminho feliz), e a config desalinhada com o ambiente real.

Se você continuar evoluindo esse projeto, a dívida técnica vai se concentrar na confiabilidade do pipeline com modelos pequenos e na escalabilidade do histórico. Esses são problemas conhecidos e gerenciáveis. O que não está em dívida é a arquitetura geral — ela está bem pensada para o problema que o projeto resolve.