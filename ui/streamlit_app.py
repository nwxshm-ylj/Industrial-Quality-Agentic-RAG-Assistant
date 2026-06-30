import json
import os
from pathlib import Path
import uuid
from typing import Any

import pandas as pd
import requests
import streamlit as st


DEFAULT_API_URL = "http://127.0.0.1:8000/api/v1/graph-chat"
API_URL = os.getenv("RAG_API_URL", DEFAULT_API_URL)
API_ROOT_URL = API_URL.partition("/api/v1/")[0]
DOCUMENTS_API_URL = f"{API_ROOT_URL}/api/v1/documents"

EVAL_REPORT_PATH = Path("data/eval/eval_report.json")


st.set_page_config(
    page_title="Industrial Agentic RAG Assistant",
    page_icon="🏭",
    layout="wide",
)


def call_graph_chat(
    question: str,
    top_k: int,
    session_id: str,
) -> dict[str, Any]:
    payload = {
        "question": question,
        "top_k": top_k,
        "session_id": session_id,
    }

    response = requests.post(
        API_URL,
        json=payload,
        timeout=180,
    )

    response.raise_for_status()
    return response.json()


def upload_knowledge_document(
    uploaded_file: Any,
    doc_type: str | None,
    version: str,
) -> dict[str, Any]:
    response = requests.post(
        f"{DOCUMENTS_API_URL}/upload",
        files={
            "file": (
                uploaded_file.name,
                uploaded_file.getvalue(),
                uploaded_file.type or "application/octet-stream",
            )
        },
        data={
            "doc_type": doc_type or "",
            "version": version,
        },
        timeout=300,
    )
    response.raise_for_status()
    return response.json()


def fetch_knowledge_documents() -> dict[str, Any]:
    response = requests.get(DOCUMENTS_API_URL, timeout=30)
    response.raise_for_status()
    return response.json()


def delete_knowledge_document(doc_id: str) -> dict[str, Any]:
    response = requests.delete(
        f"{DOCUMENTS_API_URL}/{doc_id}",
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def reindex_knowledge_document(doc_id: str) -> dict[str, Any]:
    response = requests.post(
        f"{DOCUMENTS_API_URL}/{doc_id}/reindex",
        timeout=300,
    )
    response.raise_for_status()
    return response.json()


def _request_error_message(exc: requests.RequestException) -> str:
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            detail = response.json().get("detail")
            if detail:
                return str(detail)
        except ValueError:
            pass
        return response.text or str(exc)
    return str(exc)


def load_eval_report() -> dict[str, Any] | None:
    if not EVAL_REPORT_PATH.exists():
        return None

    with EVAL_REPORT_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def render_metrics(data: dict[str, Any]) -> None:
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Intent", data.get("intent") or "-")
    col2.metric("Evidence Enough", str(data.get("evidence_enough")))
    col3.metric("Evidence Score", round(float(data.get("evidence_score") or 0), 4))
    col4.metric("Retry Count", data.get("retry_count") or 0)

    rewritten_query = data.get("rewritten_query")
    if rewritten_query:
        st.caption(f"Rewritten query: {rewritten_query}")


def render_answer(data: dict[str, Any]) -> None:
    st.subheader("回答")
    answer = data.get("answer") or "无回答"
    st.markdown(answer)


def render_citations(data: dict[str, Any]) -> None:
    st.subheader("引用来源 Citations")

    citations = data.get("citations") or []

    if not citations:
        st.info("暂无 citations。")
        return

    df = pd.DataFrame(citations)

    preferred_columns = [
        "source",
        "doc_type",
        "chunk_id",
        "score",
        "retrieval_source",
        "vector_score",
        "bm25_score",
        "hybrid_score",
        "rerank_score",
        "final_score_type",
    ]

    existing_columns = [
        col for col in preferred_columns
        if col in df.columns
    ]

    st.dataframe(
        df[existing_columns],
        use_container_width=True,
        hide_index=True,
    )


def render_contexts(data: dict[str, Any]) -> None:
    st.subheader("检索上下文 Contexts")

    contexts = data.get("contexts") or []

    if not contexts:
        st.info("暂无 contexts。")
        return

    for idx, ctx in enumerate(contexts, start=1):
        title = f"{idx}. {ctx.get('source')} | {ctx.get('doc_type')} | {ctx.get('chunk_id')}"

        with st.expander(title):
            st.write("score:", ctx.get("score"))
            st.write("retrieval_source:", ctx.get("retrieval_source"))
            st.write("hybrid_score:", ctx.get("hybrid_score"))
            st.write("rerank_score:", ctx.get("rerank_score"))
            st.markdown("**Text:**")
            st.write(ctx.get("text", ""))


def render_tool_results(data: dict[str, Any]) -> None:
    st.subheader("工具调用结果 Tool Results")

    rule_result = data.get("rule_result")
    sql_result = data.get("sql_result")
    case_result = data.get("case_result")

    has_tool_result = any([
        rule_result,
        sql_result,
        case_result,
    ])

    if not has_tool_result:
        st.info("当前问题未触发 Rule / SQL / Case Tool。")
        return

    if rule_result:
        with st.expander("Rule Tool Result", expanded=True):
            st.json(rule_result)

    if sql_result:
        with st.expander("SQL Tool Result", expanded=True):
            sql = sql_result.get("sql")
            rows = sql_result.get("rows") or []

            if sql:
                st.code(sql, language="sql")

            st.write("row_count:", sql_result.get("row_count"))

            if rows:
                st.dataframe(
                    pd.DataFrame(rows),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("SQL 查询无结果。")

    if case_result:
        with st.expander("Case Retriever Result", expanded=True):
            rows = case_result.get("rows") or []

            st.write("defect_type:", case_result.get("defect_type"))
            st.write("station:", case_result.get("station"))
            st.write("row_count:", case_result.get("row_count"))

            if rows:
                st.dataframe(
                    pd.DataFrame(rows),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("未查询到历史案例。")


def render_eval_report() -> None:
    st.subheader("评估报告摘要")

    report = load_eval_report()

    if report is None:
        st.info("暂无评估报告。请先运行：python -m scripts.evaluate_system")
        return

    metrics = report.get("metrics", {})
    results = report.get("results", [])

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total", metrics.get("total", 0))
    col2.metric("Overall Pass Rate", metrics.get("overall_pass_rate", 0))
    col3.metric("Intent Accuracy", metrics.get("intent_accuracy", 0))
    col4.metric("Avg Latency(s)", metrics.get("avg_latency_seconds", 0))

    col5, col6, col7 = st.columns(3)

    col5.metric("Doc Type Accuracy", metrics.get("doc_type_accuracy", 0))
    col6.metric("Source Accuracy", metrics.get("source_accuracy", 0))
    col7.metric("Keyword Hit Rate", metrics.get("answer_keyword_hit_rate", 0))

    if results:
        result_df = pd.DataFrame(results)

        display_columns = [
            "id",
            "question",
            "expected_intent",
            "actual_intent",
            "intent_ok",
            "doc_type_ok",
            "source_ok",
            "answer_keywords_ok",
            "all_ok",
            "latency_seconds",
        ]

        existing_columns = [
            col for col in display_columns
            if col in result_df.columns
        ]

        st.dataframe(
            result_df[existing_columns],
            use_container_width=True,
            hide_index=True,
        )


def render_knowledge_base_management() -> None:
    st.subheader("Knowledge Base Management")
    st.caption("上传、查看、删除或重建企业知识库文档索引。")

    uploaded_file = st.file_uploader(
        "上传文档",
        type=["md", "txt", "pdf", "docx"],
        key="kb_upload_file",
    )
    upload_col1, upload_col2 = st.columns(2)
    doc_type = upload_col1.text_input(
        "文档类型（可选）",
        key="kb_doc_type",
        placeholder="例如 FMEA / SOP / RULE",
    )
    version = upload_col2.text_input(
        "版本",
        value="v1",
        key="kb_version",
    )

    if st.button("上传并入库", key="kb_upload_button"):
        if uploaded_file is None:
            st.warning("请选择要上传的文档。")
        else:
            try:
                with st.spinner("正在解析并建立索引..."):
                    result = upload_knowledge_document(
                        uploaded_file=uploaded_file,
                        doc_type=doc_type.strip() or None,
                        version=version.strip() or "v1",
                    )
                st.success(
                    f"文档已入库：{result.get('doc_id')}，"
                    f"chunks={result.get('chunk_count')}"
                )
            except requests.RequestException as exc:
                st.error(f"上传失败：{_request_error_message(exc)}")

    st.markdown("---")
    try:
        document_data = fetch_knowledge_documents()
    except requests.RequestException as exc:
        st.error(f"读取文档列表失败：{_request_error_message(exc)}")
        return

    documents = document_data.get("documents") or []
    st.write(f"当前文档数：{document_data.get('total', len(documents))}")
    if not documents:
        st.info("知识库中暂无企业管理文档。")
        return

    display_columns = [
        "doc_id",
        "filename",
        "doc_type",
        "version",
        "status",
        "chunk_count",
    ]
    st.dataframe(
        pd.DataFrame(documents)[display_columns],
        use_container_width=True,
        hide_index=True,
    )

    document_options = {
        f"{doc.get('filename')} | {doc.get('doc_id')}": doc.get("doc_id")
        for doc in documents
    }
    selected_label = st.selectbox(
        "选择文档操作",
        list(document_options),
        key="kb_selected_document",
    )
    selected_doc_id = document_options[selected_label]
    action_col1, action_col2 = st.columns(2)

    if action_col1.button("重建索引", key="kb_reindex_button"):
        try:
            with st.spinner("正在重建索引..."):
                result = reindex_knowledge_document(selected_doc_id)
            st.success(result.get("message", "索引重建完成"))
            st.rerun()
        except requests.RequestException as exc:
            st.error(f"重建失败：{_request_error_message(exc)}")

    if action_col2.button("删除文档", key="kb_delete_button"):
        try:
            result = delete_knowledge_document(selected_doc_id)
            st.success(result.get("message", "文档已删除"))
            st.rerun()
        except requests.RequestException as exc:
            st.error(f"删除失败：{_request_error_message(exc)}")


def main() -> None:
    st.title("🏭 Industrial Agentic RAG Assistant")
    st.caption("工业质量知识库与设备异常诊断 Agentic RAG 系统")

    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())
    session_id = st.session_state["session_id"]

    with st.sidebar:
        st.header("配置")

        st.write("API 地址")
        st.code(API_URL)
        st.caption(f"当前 session_id: {session_id}")

        top_k = st.slider(
            "Top K",
            min_value=1,
            max_value=10,
            value=3,
            step=1,
        )

        st.markdown("---")
        st.subheader("示例问题")

        examples = [
            "ZP8 工位轮毂误识别可能是什么原因？",
            "扭矩工位连续报警应该怎么排查？",
            "合格证OCR识别VIN失败怎么办？",
            "PR001对应什么轮毂配置？",
            "最近一周ZP8工位误识别数量是多少？",
            "历史上有没有类似的轮毂误识别案例？",
            "你是谁？",
        ]

        selected_example = st.selectbox(
            "选择示例",
            examples,
            index=0,
        )

    question = st.text_area(
        "请输入你的问题",
        value=selected_example,
        height=100,
        placeholder="例如：ZP8 工位轮毂误识别可能是什么原因？",
    )

    ask_button = st.button(
        "发送问题",
        type="primary",
        use_container_width=True,
    )

    (
        tab_answer,
        tab_citations,
        tab_tools,
        tab_contexts,
        tab_eval,
        tab_kb,
        tab_raw,
    ) = st.tabs([
        "回答",
        "引用",
        "工具结果",
        "上下文",
        "评估报告",
        "Knowledge Base Management",
        "原始JSON",
    ])

    if ask_button:
        if not question.strip():
            st.warning("请输入问题。")
            return

        with st.spinner("正在调用 Agentic RAG 系统..."):
            try:
                data = call_graph_chat(
                    question=question.strip(),
                    top_k=top_k,
                    session_id=session_id,
                )

                st.session_state["last_response"] = data

            except requests.exceptions.ConnectionError:
                st.error(
                    "无法连接 FastAPI 服务。请确认已启动："
                    "uvicorn app.main:app --reload --port 8000"
                )
                return

            except requests.exceptions.Timeout:
                st.error("请求超时。可以先关闭 Reranker，或减少 top_k。")
                return

            except Exception as e:
                st.error(f"请求失败：{repr(e)}")
                return

    data = st.session_state.get("last_response")

    if data:
        with tab_answer:
            render_metrics(data)
            render_answer(data)

        with tab_citations:
            render_citations(data)

        with tab_tools:
            render_tool_results(data)

        with tab_contexts:
            render_contexts(data)

        with tab_eval:
            render_eval_report()

        with tab_raw:
            st.json(data)
    else:
        with tab_answer:
            st.info("请输入问题并点击发送。")

        with tab_eval:
            render_eval_report()

    with tab_kb:
        render_knowledge_base_management()


if __name__ == "__main__":
    main()