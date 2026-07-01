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
AUTH_LOGIN_URL = f"{API_ROOT_URL}/api/v1/auth/login"
FEEDBACK_API_URL = f"{API_ROOT_URL}/api/v1/feedback"
EVALUATION_API_URL = f"{API_ROOT_URL}/api/v1/evaluation"

EVAL_REPORT_PATH = Path("data/eval/eval_report.json")


st.set_page_config(
    page_title="Industrial Agentic RAG Assistant",
    page_icon="🏭",
    layout="wide",
)


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def login_user(username: str, password: str) -> dict[str, Any]:
    response = requests.post(
        AUTH_LOGIN_URL,
        json={"username": username, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def call_graph_chat(
    question: str,
    top_k: int,
    session_id: str,
    access_token: str,
) -> dict[str, Any]:
    payload = {
        "question": question,
        "top_k": top_k,
        "session_id": session_id,
    }
    response = requests.post(
        API_URL,
        json=payload,
        headers=_auth_headers(access_token),
        timeout=180,
    )
    response.raise_for_status()
    return response.json()


def upload_knowledge_document(
    uploaded_file: Any,
    doc_type: str | None,
    version: str,
    access_token: str,
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
        headers=_auth_headers(access_token),
        timeout=300,
    )
    response.raise_for_status()
    return response.json()


def fetch_knowledge_documents(
    access_token: str,
) -> dict[str, Any]:
    response = requests.get(
        DOCUMENTS_API_URL,
        headers=_auth_headers(access_token),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def delete_knowledge_document(
    doc_id: str,
    access_token: str,
) -> dict[str, Any]:
    response = requests.delete(
        f"{DOCUMENTS_API_URL}/{doc_id}",
        headers=_auth_headers(access_token),
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def reindex_knowledge_document(
    doc_id: str,
    access_token: str,
) -> dict[str, Any]:
    response = requests.post(
        f"{DOCUMENTS_API_URL}/{doc_id}/reindex",
        headers=_auth_headers(access_token),
        timeout=300,
    )
    response.raise_for_status()
    return response.json()


def submit_answer_feedback(
    payload: dict[str, Any],
    access_token: str,
) -> dict[str, Any]:
    response = requests.post(
        FEEDBACK_API_URL,
        json=payload,
        headers=_auth_headers(access_token),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def fetch_feedback_stats(access_token: str) -> dict[str, Any]:
    response = requests.get(
        f"{FEEDBACK_API_URL}/stats",
        headers=_auth_headers(access_token),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def fetch_feedback_list(
    access_token: str,
    rating: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": limit}
    if rating:
        params["rating"] = rating
    response = requests.get(
        FEEDBACK_API_URL,
        params=params,
        headers=_auth_headers(access_token),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def fetch_evaluation_runs(access_token: str) -> dict[str, Any]:
    response = requests.get(
        f"{EVALUATION_API_URL}/runs",
        headers=_auth_headers(access_token),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def run_evaluation_api(access_token: str) -> dict[str, Any]:
    response = requests.post(
        f"{EVALUATION_API_URL}/run",
        headers=_auth_headers(access_token),
        timeout=900,
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


def render_login() -> None:
    st.subheader("用户登录")
    st.caption("请输入企业账号访问聊天和知识库管理功能。")
    with st.form("login_form"):
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        submitted = st.form_submit_button(
            "登录",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        try:
            result = login_user(username.strip(), password)
            st.session_state["access_token"] = result["access_token"]
            st.session_state["user"] = result["user"]
            st.rerun()
        except requests.RequestException as exc:
            st.error(f"登录失败：{_request_error_message(exc)}")


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


def render_feedback_form(
    data: dict[str, Any],
    question: str,
    session_id: str,
    access_token: str,
) -> None:
    st.markdown("---")
    st.subheader("回答反馈")
    request_id = str(data.get("request_id") or "unknown")
    with st.form(f"feedback_form_{request_id}"):
        rating_label = st.radio(
            "请选择本次回答质量",
            ["👍 有用", "👎 无用", "😐 一般"],
            horizontal=True,
        )
        comment = st.text_input(
            "反馈备注（可选）",
            placeholder="例如：引用准确，但排查顺序还可以更具体",
        )
        submitted = st.form_submit_button("提交反馈")
        if submitted:
            rating_map = {
                "👍 有用": "positive",
                "👎 无用": "negative",
                "😐 一般": "neutral",
            }
            payload = {
                "request_id": data.get("request_id"),
                "session_id": data.get("session_id") or session_id,
                "question": question,
                "answer": data.get("answer") or "",
                "rating": rating_map[rating_label],
                "comment": comment or None,
                "intent": data.get("intent"),
                "citations": data.get("citations"),
                "metadata": data.get("metadata"),
            }
            try:
                submit_answer_feedback(payload, access_token)
                st.success("反馈已提交。")
            except requests.RequestException as exc:
                st.error(f"反馈提交失败：{_request_error_message(exc)}")


def render_evaluation_dashboard(access_token: str) -> None:
    st.subheader("RAG Evaluation")
    st.caption("反馈闭环、离线评估运行与质量指标")

    latest_run: dict[str, Any] | None = None
    if st.button("运行一次评估", type="primary"):
        with st.spinner("正在运行评估，可能需要数分钟..."):
            try:
                latest_run = run_evaluation_api(access_token)
                st.success(f"评估完成：{latest_run.get('run_id')}")
            except requests.RequestException as exc:
                st.error(f"评估运行失败：{_request_error_message(exc)}")

    try:
        stats = fetch_feedback_stats(access_token)
        metric_cols = st.columns(5)
        metric_cols[0].metric("正向数量", stats.get("positive_count", 0))
        metric_cols[1].metric("负向数量", stats.get("negative_count", 0))
        metric_cols[2].metric("中性数量", stats.get("neutral_count", 0))
        metric_cols[3].metric(
            "正向率",
            f"{float(stats.get('positive_rate') or 0) * 100:.1f}%",
        )
        metric_cols[4].metric(
            "负向率",
            f"{float(stats.get('negative_rate') or 0) * 100:.1f}%",
        )
        by_intent = stats.get("by_intent") or {}
        if by_intent:
            st.caption("按意图统计")
            st.dataframe(
                pd.DataFrame(
                    [
                        {"intent": intent, "count": count}
                        for intent, count in by_intent.items()
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
    except requests.RequestException as exc:
        st.error(f"反馈统计加载失败：{_request_error_message(exc)}")

    st.markdown("#### 最近反馈")
    rating_label = st.selectbox(
        "按 rating 过滤",
        ["全部", "positive", "negative", "neutral"],
    )
    try:
        feedback = fetch_feedback_list(
            access_token,
            rating=None if rating_label == "全部" else rating_label,
            limit=100,
        )
        if feedback:
            feedback_df = pd.DataFrame(feedback)
            columns = [
                column for column in [
                    "created_at", "username", "rating", "intent",
                    "question", "comment", "request_id",
                ]
                if column in feedback_df.columns
            ]
            st.dataframe(
                feedback_df[columns],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("暂无反馈记录。")
    except requests.RequestException as exc:
        st.error(f"反馈列表加载失败：{_request_error_message(exc)}")

    st.markdown("#### 评估运行")
    try:
        run_payload = fetch_evaluation_runs(access_token)
        runs = run_payload.get("runs") or []
        if latest_run is None and runs:
            latest_run = runs[0]

        if latest_run:
            cols = st.columns(5)
            cols[0].metric(
                "Intent Accuracy",
                f"{float(latest_run.get('intent_accuracy') or 0) * 100:.1f}%",
            )
            cols[1].metric(
                "Source Hit Rate",
                f"{float(latest_run.get('source_hit_rate') or 0) * 100:.1f}%",
            )
            cols[2].metric(
                "Keyword Hit Rate",
                f"{float(latest_run.get('answer_keyword_hit_rate') or 0) * 100:.1f}%",
            )
            cols[3].metric(
                "Memory Follow-up",
                f"{float(latest_run.get('memory_followup_success_rate') or 0) * 100:.1f}%",
            )
            cols[4].metric(
                "Avg Latency(ms)",
                round(float(latest_run.get("avg_latency_ms") or 0), 2),
            )

        if runs:
            runs_df = pd.DataFrame(runs)
            columns = [
                column for column in [
                    "run_id", "created_at", "username", "status",
                    "total_questions", "intent_accuracy",
                    "source_hit_rate", "answer_keyword_hit_rate",
                    "memory_followup_success_rate", "avg_latency_ms",
                ]
                if column in runs_df.columns
            ]
            st.dataframe(
                runs_df[columns],
                use_container_width=True,
                hide_index=True,
            )
        elif latest_run is None:
            st.info("暂无评估运行记录。")
    except requests.RequestException as exc:
        st.error(f"评估运行列表加载失败：{_request_error_message(exc)}")


def render_knowledge_base_management(
    access_token: str,
    user_role: str,
) -> None:
    st.subheader("Knowledge Base Management")
    st.caption("上传、查看、删除或重建企业知识库文档索引。")

    can_upload = user_role in {"admin", "engineer"}
    if can_upload:
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
                            access_token=access_token,
                        )
                    st.success(
                        f"文档已入库：{result.get('doc_id')}，"
                        f"chunks={result.get('chunk_count')}"
                    )
                except requests.RequestException as exc:
                    st.error(f"上传失败：{_request_error_message(exc)}")
    else:
        st.info("viewer 角色仅可查看知识库文档。")

    st.markdown("---")
    try:
        document_data = fetch_knowledge_documents(access_token)
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

    if user_role != "admin":
        if user_role == "engineer":
            st.caption("engineer 可以上传和查看，删除与重建仅限 admin。")
        return

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
                result = reindex_knowledge_document(
                    selected_doc_id,
                    access_token,
                )
            st.success(result.get("message", "索引重建完成"))
            st.rerun()
        except requests.RequestException as exc:
            st.error(f"重建失败：{_request_error_message(exc)}")

    if action_col2.button("删除文档", key="kb_delete_button"):
        try:
            result = delete_knowledge_document(
                selected_doc_id,
                access_token,
            )
            st.success(result.get("message", "文档已删除"))
            st.rerun()
        except requests.RequestException as exc:
            st.error(f"删除失败：{_request_error_message(exc)}")


def main() -> None:
    st.title("🏭 Industrial Agentic RAG Assistant")
    st.caption("工业质量知识库与设备异常诊断 Agentic RAG 系统")

    access_token = st.session_state.get("access_token")
    current_user = st.session_state.get("user")
    if not access_token or not current_user:
        st.info("请先登录后使用系统。")
        render_login()
        return

    user_role = current_user.get("role", "viewer")
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())
    session_id = st.session_state["session_id"]

    with st.sidebar:
        st.header("当前用户")
        st.write(f"{current_user.get('username')} ({user_role})")
        if st.button("退出登录", use_container_width=True):
            for key in (
                "access_token",
                "user",
                "last_response",
                "last_question",
            ):
                st.session_state.pop(key, None)
            st.rerun()

        st.markdown("---")
        st.header("配置")
        st.write("API 地址")
        st.code(API_URL)
        st.caption(f"当前 session_id: {session_id}")
        top_k = st.slider("Top K", 1, 10, 3, 1)

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
        selected_example = st.selectbox("选择示例", examples, index=0)

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

    tab_names = ["回答", "引用", "工具结果", "上下文"]
    if user_role in {"admin", "engineer"}:
        tab_names.append("RAG Evaluation")
    tab_names.extend(["Knowledge Base Management", "原始JSON"])
    tab_handles = dict(zip(tab_names, st.tabs(tab_names)))

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
                    access_token=access_token,
                )
                st.session_state["last_response"] = data
                st.session_state["last_question"] = question.strip()
            except requests.exceptions.ConnectionError:
                st.error(
                    "无法连接 FastAPI 服务。请确认已启动："
                    "uvicorn app.main:app --reload --port 8000"
                )
                return
            except requests.exceptions.Timeout:
                st.error("请求超时。可以先关闭 Reranker，或减少 top_k。")
                return
            except requests.HTTPError as exc:
                st.error(f"请求失败：{_request_error_message(exc)}")
                return
            except Exception as exc:
                st.error(f"请求失败：{repr(exc)}")
                return

    data = st.session_state.get("last_response")
    last_question = st.session_state.get("last_question", "")
    if data:
        with tab_handles["回答"]:
            render_metrics(data)
            render_answer(data)
            render_feedback_form(
                data=data,
                question=last_question,
                session_id=session_id,
                access_token=access_token,
            )
        with tab_handles["引用"]:
            render_citations(data)
        with tab_handles["工具结果"]:
            render_tool_results(data)
        with tab_handles["上下文"]:
            render_contexts(data)
        with tab_handles["原始JSON"]:
            st.json(data)
    else:
        with tab_handles["回答"]:
            st.info("请输入问题并点击发送。")

    if "RAG Evaluation" in tab_handles:
        with tab_handles["RAG Evaluation"]:
            render_evaluation_dashboard(access_token)

    with tab_handles["Knowledge Base Management"]:
        render_knowledge_base_management(
            access_token=access_token,
            user_role=user_role,
        )


if __name__ == "__main__":
    main()