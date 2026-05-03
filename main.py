from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from core.solver import CodeSolver, ContextItem, SolveRequest


BASE_DIR = Path(__file__).resolve().parent
console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="code-solver",
        description="Resolve problemas de programação localmente com Ollama.",
    )
    parser.add_argument("problem", nargs="?", help="Descrição direta do problema.")
    parser.add_argument("--problem-file", help="Arquivo .txt/.md com um único problema.")
    parser.add_argument("--batch-file", help="Arquivo .txt/.md com múltiplos problemas.")
    parser.add_argument(
        "--context-file",
        action="append",
        default=[],
        help="Arquivo(s) de código ou contexto para enviar junto.",
    )
    parser.add_argument(
        "--language",
        default="python",
        help="Linguagem alvo principal (python, javascript, typescript, java, go, rust).",
    )
    parser.add_argument("--model", help="Modelo Ollama específico.")
    parser.add_argument("--mode", choices=["fast", "deep"], default="fast")
    parser.add_argument("--interactive", action="store_true", help="Abre modo interativo.")
    parser.add_argument("--list-models", action="store_true", help="Lista modelos disponíveis.")
    parser.add_argument(
        "--compare-models",
        nargs="+",
        help="Roda o mesmo problema em múltiplos modelos e mostra um resumo.",
    )
    parser.add_argument(
        "--export-dir",
        default=None,
        help="Diretório para exportar markdown, código, testes e metadata.",
    )
    parser.add_argument("--no-cache", action="store_true", help="Ignora o cache local.")
    parser.add_argument("--json", action="store_true", help="Imprime resultado bruto em JSON.")
    return parser


def read_text_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore").strip()


def build_context_items(paths: Iterable[str]) -> list[ContextItem]:
    items: list[ContextItem] = []
    for raw_path in paths:
        path = Path(raw_path)
        items.append(
            ContextItem(
                name=path.name,
                content=path.read_text(encoding="utf-8", errors="ignore"),
            )
        )
    return items


def resolve_problem_argument(args: argparse.Namespace) -> str | None:
    if args.problem_file:
        return read_text_file(args.problem_file)
    if args.problem:
        return args.problem.strip()
    return None


def render_result(result, export_paths: dict[str, str] | None = None) -> None:
    header = Table.grid(padding=(0, 2))
    header.add_row("Classificação", result.classification)
    header.add_row("Complexidade", str(result.complexity))
    header.add_row("Labels", ", ".join(result.labels))
    header.add_row("Modelo", result.model)
    header.add_row("Modo", result.mode)
    header.add_row("Cache", "sim" if result.cached else "não")
    console.print(Panel.fit(header, title="Resumo"))
    console.print(Markdown(result.markdown))
    if export_paths:
        export_table = Table(title="Arquivos exportados")
        export_table.add_column("Tipo")
        export_table.add_column("Caminho")
        for key, value in export_paths.items():
            export_table.add_row(key, value)
        console.print(export_table)


def solve_single(
    solver: CodeSolver,
    problem: str,
    args: argparse.Namespace,
    model_override: str | None = None,
) -> None:
    request = SolveRequest(
        problem=problem,
        language=args.language,
        model=model_override or args.model,
        mode=args.mode,
        context_items=build_context_items(args.context_file),
        use_cache=not args.no_cache,
    )
    result = solver.solve(request)
    export_paths = None
    if args.export_dir:
        export_paths = solver.export_result(result, BASE_DIR / args.export_dir)
    if args.json:
        payload = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
        sys.stdout.buffer.write(payload.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
        return
    render_result(result, export_paths)


def solve_batch(solver: CodeSolver, args: argparse.Namespace) -> None:
    batch_text = read_text_file(args.batch_file)
    problems = solver.parse_batch_text(batch_text)
    if not problems:
        raise ValueError("Nenhum problema válido foi encontrado no arquivo batch.")

    summary = Table(title="Resumo do batch")
    summary.add_column("#")
    summary.add_column("Classificação")
    summary.add_column("Complexidade")
    summary.add_column("Status")
    summary.add_column("Modelo")

    for index, problem in enumerate(problems, start=1):
        request = SolveRequest(
            problem=problem,
            language=args.language,
            model=args.model,
            mode=args.mode,
            context_items=build_context_items(args.context_file),
            use_cache=not args.no_cache,
        )
        result = solver.solve(request)
        if args.export_dir:
            solver.export_result(
                result,
                BASE_DIR / args.export_dir,
                slug=f"batch-{index:02d}",
            )
        summary.add_row(
            str(index),
            result.classification,
            str(result.complexity),
            result.validation.get("status", "n/a"),
            result.model,
        )
    console.print(summary)


def compare_models(solver: CodeSolver, problem: str, args: argparse.Namespace) -> None:
    comparison = Table(title="Comparação de modelos")
    comparison.add_column("Modelo")
    comparison.add_column("Classificação")
    comparison.add_column("Complexidade")
    comparison.add_column("Validação")
    comparison.add_column("Labels")

    for model_name in args.compare_models:
        request = SolveRequest(
            problem=problem,
            language=args.language,
            model=model_name,
            mode=args.mode,
            context_items=build_context_items(args.context_file),
            use_cache=not args.no_cache,
        )
        result = solver.solve(request)
        comparison.add_row(
            model_name,
            result.classification,
            str(result.complexity),
            result.validation.get("status", "n/a"),
            ", ".join(result.labels),
        )
        if args.export_dir:
            solver.export_result(
                result,
                BASE_DIR / args.export_dir,
                slug=model_name.replace(":", "-").replace("/", "-"),
            )
    console.print(comparison)


def run_interactive(solver: CodeSolver, args: argparse.Namespace) -> None:
    console.print("[bold green]Modo interativo iniciado.[/bold green] Digite uma linha vazia para sair.")
    while True:
        problem = console.input("\n[bold cyan]Problema[/bold cyan]> ").strip()
        if not problem:
            console.print("Encerrando.")
            break
        try:
            solve_single(solver, problem, args)
        except Exception as exc:
            console.print(f"[bold red]Erro:[/bold red] {exc}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        solver = CodeSolver.from_config(BASE_DIR / "config.yaml")

        if args.list_models:
            models = solver.available_models()
            model_table = Table(title="Modelos disponíveis")
            model_table.add_column("Nome")
            for model_name in models:
                model_table.add_row(model_name)
            console.print(model_table)
            return

        if args.batch_file:
            solve_batch(solver, args)
            return

        if args.interactive:
            run_interactive(solver, args)
            return

        problem = resolve_problem_argument(args)
        if not problem:
            parser.error("Informe um problema, --problem-file, --batch-file ou use --interactive.")

        if args.compare_models:
            compare_models(solver, problem, args)
            return

        solve_single(solver, problem, args)
    except Exception as exc:
        console.print(f"[bold red]Erro:[/bold red] {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
