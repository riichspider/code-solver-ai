from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.solver import CodeSolver, ContextItem, SolveRequest


BASE_DIR = Path(__file__).resolve().parent


@st.cache_resource
def get_solver() -> CodeSolver:
    return CodeSolver.from_config(BASE_DIR / "config.yaml")


def uploaded_file_to_context(uploaded_file) -> ContextItem:
    return ContextItem(
        name=uploaded_file.name,
        content=uploaded_file.getvalue().decode("utf-8", errors="ignore"),
    )


def render_exception(exc: Exception) -> None:
    # Handle specific error types with friendly messages
    if isinstance(exc, ConnectionError):
        st.error("❌ Falha de conexão com o modelo")
        st.caption("Verifique se o Ollama está ativo e acessível.")
    elif isinstance(exc, FileNotFoundError):
        st.error("❌ Arquivo ou modelo não encontrado")
        st.caption("Verifique se o modelo especificado está instalado no Ollama.")
    elif isinstance(exc, PermissionError):
        st.error("❌ Permissão negada")
        st.caption("Verifique as permissões de acesso aos arquivos e diretórios.")
    elif isinstance(exc, ValueError):
        st.error("❌ Valor inválido fornecido")
        st.caption("Verifique se os parâmetros informados estão corretos.")
    elif isinstance(exc, RuntimeError):
        st.error("❌ Erro de execução")
        st.caption("Ocorreu um erro durante o processamento da solicitação.")
    else:
        st.error("❌ Não foi possível concluir a execução.")
        st.caption(
            "Verifique se o Ollama está ativo, se o modelo existe e se o prompt tem contexto suficiente."
        )

    with st.expander("Detalhes técnicos"):
        st.code(f"{type(exc).__name__}: {str(exc)}")


def render_single_result(result) -> None:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Classificação", result.classification)
    col2.metric("Complexidade", result.complexity)
    col3.metric("Validação", result.validation.get("status", "n/a"))
    col4.metric("Cache", "Sim" if result.cached else "Não")

    st.caption(
        f"Modelo: `{result.model}` · Labels: {', '.join(result.labels)}")

    overview, code_tab, tests_tab, markdown_tab, memory_tab = st.tabs(
        ["Visão geral", "Código", "Testes", "Markdown", "Memória"]
    )

    with overview:
        st.markdown(result.markdown)

    with code_tab:
        st.code(result.code, language=result.language)
        st.download_button(
            "Baixar código",
            data=result.code,
            file_name=result.filename,
            mime="text/plain",
        )

    with tests_tab:
        st.code(result.tests, language=result.language)
        st.download_button(
            "Baixar testes",
            data=result.tests,
            file_name=result.test_filename,
            mime="text/plain",
        )

    with markdown_tab:
        st.code(result.markdown, language="markdown")
        st.download_button(
            "Baixar relatório",
            data=result.markdown,
            file_name="solution.md",
            mime="text/markdown",
        )

    with memory_tab:
        if not result.similar_context:
            st.info("Nenhuma solução parecida encontrada no histórico ainda.")
        else:
            for item in result.similar_context:
                with st.expander(
                    f"Score {item['score']:.2f} · {item['classification']} · {item['language']}"
                ):
                    st.write(item["problem"])
                    st.code(item["solution_excerpt"], language="markdown")


def main() -> None:
    st.set_page_config(
        page_title="Code Solver AI",
        page_icon="🧠",
        layout="wide",
    )
    st.title("🧠 Code Solver AI")
    st.caption(
        "Resolução local de problemas de programação com Ollama e histórico persistente.")

    solver = get_solver()
    available_models = solver.available_models() or [solver.default_model]

    with st.sidebar:
        st.header("Configurações")
        selected_model = st.selectbox(
            "Modelo",
            options=available_models,
            index=0,
        )
        mode = st.radio("Modo", options=["fast", "deep"], horizontal=True)
        language = st.selectbox("Linguagem principal",
                                options=solver.supported_languages)
        use_cache = st.checkbox("Usar cache", value=True)
        export_files = st.checkbox("Exportar resultado em disco", value=False)
        batch_file = st.file_uploader(
            "Arquivo batch (.txt/.md)", type=["txt", "md"])
        uploaded_context = st.file_uploader(
            "Arquivos de contexto",
            accept_multiple_files=True,
            type=None,
        )

    problem = st.text_area(
        "Descreva o problema",
        height=220,
        placeholder="Cole o bug, requisito, algoritmo, refactor ou dúvida aqui.",
    )
    inline_code = st.text_area(
        "Código opcional",
        height=180,
        placeholder="Cole aqui o trecho de código existente, stack trace ou contexto adicional.",
    )

    if st.button("Resolver agora", type="primary", use_container_width=True):
        try:
            context_items = [uploaded_file_to_context(
                item) for item in uploaded_context or []]
            if inline_code.strip():
                context_items.append(ContextItem(
                    name="inline_context.txt", content=inline_code))

            if batch_file is not None:
                batch_text = batch_file.getvalue().decode("utf-8", errors="ignore")
                problems = solver.parse_batch_text(batch_text)
                if not problems:
                    st.warning(
                        "Nenhum problema válido encontrado no arquivo batch.")
                    return
                st.success(f"{len(problems)} problema(s) carregado(s).")
                for index, batch_problem in enumerate(problems, start=1):
                    request = SolveRequest(
                        problem=batch_problem,
                        language=language,
                        model=selected_model,
                        mode=mode,
                        context_items=context_items,
                        use_cache=use_cache,
                    )
                    result = solver.solve(request)
                    if export_files:
                        solver.export_result(
                            result,
                            BASE_DIR / solver.export_directory,
                            slug=f"streamlit-batch-{index:02d}",
                        )
                    with st.expander(f"Problema {index}: {result.classification}", expanded=index == 1):
                        render_single_result(result)
                return

            if not problem.strip():
                st.warning("Informe um problema ou envie um arquivo batch.")
                return

            request = SolveRequest(
                problem=problem,
                language=language,
                model=selected_model,
                mode=mode,
                context_items=context_items,
                use_cache=use_cache,
            )
            result = solver.solve(request)
            if export_files:
                solver.export_result(result, BASE_DIR /
                                     solver.export_directory)
            render_single_result(result)
        except Exception as exc:
            render_exception(exc)


if __name__ == "__main__":
    main()
