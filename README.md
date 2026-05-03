# Code Solver AI

Ferramenta local para analisar problemas de programação e devolver uma resposta estruturada com:

- classificação automática do problema
- análise passo a passo
- solução completa em código
- testes
- validação local segura
- relatório final em Markdown
- labels sugeridas para GitHub

Tudo roda offline com modelos locais via Ollama.

## Stack

- Python 3.11+
- CLI com `argparse` + `rich`
- Web UI com Streamlit
- Backend local via Ollama
- Cache em JSON
- Histórico persistente em SQLite

## Estrutura

```text
.
├── main.py
├── app.py
├── core/
├── models/
├── utils/
├── db/
├── tests/
├── examples/
├── config.yaml
├── requirements.txt
└── README.md
```

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows PowerShell
pip install -r requirements.txt
```

Se quiser o comando `code-solver` direto no terminal:

```bash
pip install -e .
```

## Configuração do Ollama

1. Instale o Ollama.
2. Inicie o serviço local.
3. Baixe pelo menos um modelo de código.

Exemplos:

```bash
ollama pull qwen2.5-coder:7b
ollama pull codellama:13b
ollama pull deepseek-coder-v2
```

O `config.yaml` já vem apontando para `http://localhost:11434/api`.

## Uso via CLI

Resolver um problema direto:

```bash
code-solver "Corrija uma função Python que falha ao remover duplicados preservando a ordem."
```

Sem instalar como pacote:

```bash
python main.py "Implemente busca binária iterativa em Python com testes."
```

Com arquivo de contexto:

```bash
python main.py "Corrija o bug" --context-file examples/context_example.py
```

Modo profundo:

```bash
python main.py "Otimize este algoritmo" --mode deep --model qwen2.5-coder:7b
```

Modo batch:

```bash
python main.py --batch-file examples/problems.md --export-dir exports
```

Comparação de modelos:

```bash
python main.py "Refatore esta função" --compare-models qwen2.5-coder:7b codellama:13b
```

Listar modelos disponíveis no Ollama:

```bash
python main.py --list-models
```

## Uso via Web UI

```bash
streamlit run app.py
```

Na interface você pode:

- colar o problema
- anexar arquivos de contexto
- alternar entre `fast` e `deep`
- escolher o modelo
- processar batch `.txt` ou `.md`
- baixar código, testes e relatório

## Pipeline

1. Entendimento do problema
2. Classificação + complexidade
3. Plano de solução
4. Geração de código
5. Validação local segura
6. Formatação do relatório final

Se a validação falhar, o sistema tenta uma rodada de correção automática antes de encerrar.

## Cache e histórico

- Cache: `db/cache/*.json`
- Histórico: `db/history.db`

O histórico é usado como memória contextual para reaproveitar soluções similares.

## Exportação

Cada execução pode gerar:

- `solution.md`
- arquivo principal de código
- arquivo de testes
- `metadata.json`

Os arquivos são salvos em `exports/` por padrão.

## Modelos recomendados

- `qwen2.5-coder:7b`
- `deepseek-coder-v2`
- `codellama:13b`
- `llama3.2`
- `gemma2`
- `phi3`

## Testes

```bash
python -m pytest
```

## Observações

- O projeto é 100% local e não usa APIs pagas.
- A integração foi implementada em cima dos endpoints locais `/api/chat` e `/api/tags` do Ollama.
- Para linguagens além de Python, a validação automática é best-effort e pode depender de runtimes instalados no sistema.
