from datetime import datetime, timedelta
import random

from sqlalchemy import text

from app.core.security import hash_password
from app.db.session import engine


def create_tables():
    ddl = """
    DROP TABLE IF EXISTS inspection_record;
    DROP TABLE IF EXISTS equipment_alarm;
    DROP TABLE IF EXISTS quality_cases;

    CREATE TABLE inspection_record (
        record_id SERIAL PRIMARY KEY,
        vin VARCHAR(100),
        station VARCHAR(100),
        item VARCHAR(100),
        ai_result VARCHAR(100),
        mes_result VARCHAR(100),
        is_match BOOLEAN,
        confidence NUMERIC,
        created_at TIMESTAMP
    );

    CREATE TABLE equipment_alarm (
        alarm_id SERIAL PRIMARY KEY,
        equipment_id VARCHAR(100),
        station VARCHAR(100),
        alarm_code VARCHAR(100),
        alarm_level VARCHAR(50),
        sensor_value NUMERIC,
        resolved_action TEXT,
        created_at TIMESTAMP
    );

    CREATE TABLE quality_cases (
        case_id SERIAL PRIMARY KEY,
        station VARCHAR(100),
        defect_type VARCHAR(100),
        phenomenon TEXT,
        root_cause TEXT,
        action TEXT,
        model_type VARCHAR(100),
        part_code VARCHAR(100),
        created_at TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS conversation_messages (
        id SERIAL PRIMARY KEY,
        session_id VARCHAR(100) NOT NULL,
        role VARCHAR(20) NOT NULL,
        content TEXT NOT NULL,
        intent VARCHAR(50),
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS documents (
        id SERIAL PRIMARY KEY,
        doc_id VARCHAR(100) UNIQUE NOT NULL,
        filename VARCHAR(255) NOT NULL,
        original_filename VARCHAR(255),
        doc_type VARCHAR(50),
        file_ext VARCHAR(20),
        file_path TEXT,
        version VARCHAR(50) DEFAULT 'v1',
        status VARCHAR(50) DEFAULT 'indexed',
        chunk_count INT DEFAULT 0,
        content_hash VARCHAR(128),
        failed_stage VARCHAR(100),
        error_message TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );

    ALTER TABLE documents
        ADD COLUMN IF NOT EXISTS failed_stage VARCHAR(100);
    ALTER TABLE documents
        ADD COLUMN IF NOT EXISTS error_message TEXT;

    CREATE TABLE IF NOT EXISTS document_chunks (
        id SERIAL PRIMARY KEY,
        doc_id VARCHAR(100) NOT NULL,
        chunk_id VARCHAR(150) UNIQUE NOT NULL,
        chunk_index INT NOT NULL,
        text TEXT NOT NULL,
        doc_type VARCHAR(50),
        source VARCHAR(255),
        version VARCHAR(50),
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_documents_doc_id
        ON documents (doc_id);
    CREATE INDEX IF NOT EXISTS idx_documents_content_hash
        ON documents (content_hash);
    CREATE INDEX IF NOT EXISTS idx_document_chunks_doc_id
        ON document_chunks (doc_id);
    CREATE INDEX IF NOT EXISTS idx_document_chunks_chunk_id
        ON document_chunks (chunk_id);

    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(100) UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role VARCHAR(50) NOT NULL DEFAULT 'viewer',
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        CONSTRAINT users_role_check
            CHECK (role IN ('admin', 'engineer', 'viewer'))
    );

    CREATE TABLE IF NOT EXISTS operation_audit_logs (
        id SERIAL PRIMARY KEY,
        request_id VARCHAR(100),
        session_id VARCHAR(100),
        username VARCHAR(100),
        role VARCHAR(50),
        action VARCHAR(100) NOT NULL,
        resource_type VARCHAR(100),
        resource_id VARCHAR(150),
        status VARCHAR(50),
        detail TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_audit_request_id
        ON operation_audit_logs (request_id);
    CREATE INDEX IF NOT EXISTS idx_audit_username
        ON operation_audit_logs (username);
    CREATE INDEX IF NOT EXISTS idx_audit_created_at
        ON operation_audit_logs (created_at);

    CREATE TABLE IF NOT EXISTS answer_feedback (
        id SERIAL PRIMARY KEY,
        request_id VARCHAR(100),
        session_id VARCHAR(100),
        username VARCHAR(100),
        role VARCHAR(50),
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        rating VARCHAR(20) NOT NULL,
        comment TEXT,
        intent VARCHAR(50),
        citations TEXT,
        metadata TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        CONSTRAINT answer_feedback_rating_check
            CHECK (rating IN ('positive', 'negative', 'neutral'))
    );

    CREATE INDEX IF NOT EXISTS idx_answer_feedback_request_id
        ON answer_feedback (request_id);
    CREATE INDEX IF NOT EXISTS idx_answer_feedback_username
        ON answer_feedback (username);
    CREATE INDEX IF NOT EXISTS idx_answer_feedback_rating
        ON answer_feedback (rating);
    CREATE INDEX IF NOT EXISTS idx_answer_feedback_created_at
        ON answer_feedback (created_at);

    CREATE TABLE IF NOT EXISTS rag_eval_runs (
        id SERIAL PRIMARY KEY,
        run_id VARCHAR(100) UNIQUE NOT NULL,
        username VARCHAR(100),
        status VARCHAR(50) DEFAULT 'completed',
        total_questions INT DEFAULT 0,
        intent_accuracy FLOAT,
        source_hit_rate FLOAT,
        answer_keyword_hit_rate FLOAT,
        memory_followup_success_rate FLOAT,
        avg_latency_ms FLOAT,
        report_path TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS rag_eval_items (
        id SERIAL PRIMARY KEY,
        run_id VARCHAR(100) NOT NULL,
        question_id VARCHAR(100),
        question TEXT NOT NULL,
        expected_intent VARCHAR(50),
        actual_intent VARCHAR(50),
        expected_keywords TEXT,
        keyword_hit BOOLEAN,
        expected_sources TEXT,
        source_hit BOOLEAN,
        answer TEXT,
        latency_ms FLOAT,
        passed BOOLEAN,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_rag_eval_runs_run_id
        ON rag_eval_runs (run_id);
    CREATE INDEX IF NOT EXISTS idx_rag_eval_runs_created_at
        ON rag_eval_runs (created_at);
    CREATE INDEX IF NOT EXISTS idx_rag_eval_items_run_id
        ON rag_eval_items (run_id);

    CREATE TABLE IF NOT EXISTS rag_request_runs (
        id BIGSERIAL PRIMARY KEY,
        request_id VARCHAR(100) UNIQUE NOT NULL,
        trace_id VARCHAR(100),
        session_id VARCHAR(100),
        username VARCHAR(100),
        role VARCHAR(50),
        route VARCHAR(255),
        method VARCHAR(20),
        intent VARCHAR(50),
        status VARCHAR(50) NOT NULL,
        http_status INT,
        total_latency_ms FLOAT,
        evidence_score FLOAT,
        evidence_enough BOOLEAN,
        retry_count INT DEFAULT 0,
        retrieval_mode VARCHAR(50),
        degraded BOOLEAN DEFAULT false,
        degraded_reason TEXT,
        context_count INT DEFAULT 0,
        citation_count INT DEFAULT 0,
        llm_call_count INT DEFAULT 0,
        input_tokens BIGINT DEFAULT 0,
        output_tokens BIGINT DEFAULT 0,
        total_tokens BIGINT DEFAULT 0,
        embedding_tokens BIGINT DEFAULT 0,
        calculated_cost NUMERIC(18, 8) DEFAULT 0,
        currency VARCHAR(20),
        error_type VARCHAR(150),
        metadata TEXT,
        started_at TIMESTAMP NOT NULL,
        completed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS ai_usage_events (
        id BIGSERIAL PRIMARY KEY,
        event_id VARCHAR(100) UNIQUE NOT NULL,
        request_id VARCHAR(100) NOT NULL,
        trace_id VARCHAR(100),
        component VARCHAR(100) NOT NULL,
        operation VARCHAR(100) NOT NULL,
        provider VARCHAR(100) NOT NULL,
        model VARCHAR(150) NOT NULL,
        status VARCHAR(50) NOT NULL,
        latency_ms FLOAT,
        input_tokens BIGINT,
        output_tokens BIGINT,
        total_tokens BIGINT,
        input_text_count INT,
        input_char_count BIGINT,
        cost NUMERIC(18, 8),
        currency VARCHAR(20),
        pricing_version VARCHAR(100),
        measurement_source VARCHAR(50),
        error_type VARCHAR(150),
        metadata TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS retrieval_events (
        id BIGSERIAL PRIMARY KEY,
        event_id VARCHAR(100) UNIQUE NOT NULL,
        request_id VARCHAR(100) NOT NULL,
        trace_id VARCHAR(100),
        operation VARCHAR(100) NOT NULL,
        status VARCHAR(50) NOT NULL,
        latency_ms FLOAT,
        top_k INT,
        vector_hit_count INT DEFAULT 0,
        keyword_hit_count INT DEFAULT 0,
        fused_hit_count INT DEFAULT 0,
        returned_count INT DEFAULT 0,
        reranker_used BOOLEAN DEFAULT false,
        retrieval_mode VARCHAR(50),
        degraded BOOLEAN DEFAULT false,
        degraded_reason TEXT,
        qdrant_latency_ms FLOAT,
        opensearch_latency_ms FLOAT,
        fusion_latency_ms FLOAT,
        reranker_latency_ms FLOAT,
        collection_name VARCHAR(150),
        keyword_index VARCHAR(150),
        embedding_index_version VARCHAR(100),
        error_type VARCHAR(150),
        query_hash VARCHAR(128),
        metadata TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_rag_request_runs_created_at
        ON rag_request_runs (created_at);
    CREATE INDEX IF NOT EXISTS idx_rag_request_runs_intent
        ON rag_request_runs (intent);
    CREATE INDEX IF NOT EXISTS idx_rag_request_runs_status
        ON rag_request_runs (status);
    CREATE INDEX IF NOT EXISTS idx_rag_request_runs_username
        ON rag_request_runs (username);
    CREATE INDEX IF NOT EXISTS idx_rag_request_runs_trace_id
        ON rag_request_runs (trace_id);
    CREATE INDEX IF NOT EXISTS idx_rag_request_runs_session_id
        ON rag_request_runs (session_id);
    CREATE INDEX IF NOT EXISTS idx_ai_usage_events_request_id
        ON ai_usage_events (request_id);
    CREATE INDEX IF NOT EXISTS idx_ai_usage_events_created_at
        ON ai_usage_events (created_at);
    CREATE INDEX IF NOT EXISTS idx_ai_usage_events_model
        ON ai_usage_events (provider, model);
    CREATE INDEX IF NOT EXISTS idx_retrieval_events_request_id
        ON retrieval_events (request_id);
    CREATE INDEX IF NOT EXISTS idx_retrieval_events_created_at
        ON retrieval_events (created_at);
    CREATE INDEX IF NOT EXISTS idx_retrieval_events_mode
        ON retrieval_events (retrieval_mode, degraded);
    """

    with engine.begin() as conn:
        conn.execute(text(ddl))


def ensure_default_admin() -> None:
    password_hash = hash_password("admin123")
    query = text("""
        INSERT INTO users (username, password_hash, role, is_active)
        VALUES (:username, :password_hash, 'admin', true)
        ON CONFLICT (username) DO NOTHING
    """)

    with engine.begin() as conn:
        conn.execute(
            query,
            {
                "username": "admin",
                "password_hash": password_hash,
            },
        )


def insert_sample_data():
    stations = ["ZP8", "ZP7", "ZP6", "TORQUE01", "OCR01"]
    inspection_items = ["wheel", "mirror", "badge", "glass", "door_panel"]
    alarm_codes = ["TQ001", "TQ002", "CAM001", "OCR001", "NET001"]
    defect_types = ["wheel_misrecognition", "ocr_vin_failure", "torque_alarm", "config_mismatch"]

    now = datetime.now()

    with engine.begin() as conn:
        # inspection_record: AI视觉检测记录
        for i in range(1000):
            station = random.choice(["ZP8", "ZP8", "ZP7", "ZP6"])
            item = random.choice(inspection_items)

            is_match = random.random() > 0.15
            confidence = round(random.uniform(0.55, 0.99), 3)

            ai_result = random.choice(["OK", "NG", "wheel_type_a", "wheel_type_b"])
            mes_result = ai_result if is_match else random.choice(["OK", "NG", "wheel_type_c"])

            created_at = now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))

            conn.execute(
                text("""
                    INSERT INTO inspection_record
                    (vin, station, item, ai_result, mes_result, is_match, confidence, created_at)
                    VALUES
                    (:vin, :station, :item, :ai_result, :mes_result, :is_match, :confidence, :created_at)
                """),
                {
                    "vin": f"LSV{i:014d}",
                    "station": station,
                    "item": item,
                    "ai_result": ai_result,
                    "mes_result": mes_result,
                    "is_match": is_match,
                    "confidence": confidence,
                    "created_at": created_at,
                }
            )

        # equipment_alarm: 设备报警记录
        for i in range(800):
            station = random.choice(stations)
            alarm_code = random.choice(alarm_codes)
            alarm_level = random.choice(["LOW", "MEDIUM", "HIGH"])

            created_at = now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))

            conn.execute(
                text("""
                    INSERT INTO equipment_alarm
                    (equipment_id, station, alarm_code, alarm_level, sensor_value, resolved_action, created_at)
                    VALUES
                    (:equipment_id, :station, :alarm_code, :alarm_level, :sensor_value, :resolved_action, :created_at)
                """),
                {
                    "equipment_id": f"EQ-{station}-{random.randint(1, 5)}",
                    "station": station,
                    "alarm_code": alarm_code,
                    "alarm_level": alarm_level,
                    "sensor_value": round(random.uniform(0, 100), 2),
                    "resolved_action": random.choice([
                        "检查设备状态",
                        "复位后恢复",
                        "更换套筒",
                        "调整相机曝光",
                        "检查网络连接",
                    ]),
                    "created_at": created_at,
                }
            )

        # quality_cases: 历史质量案例
        for i in range(100):
            defect_type = random.choice(defect_types)
            station = random.choice(stations)

            conn.execute(
                text("""
                    INSERT INTO quality_cases
                    (station, defect_type, phenomenon, root_cause, action, model_type, part_code, created_at)
                    VALUES
                    (:station, :defect_type, :phenomenon, :root_cause, :action, :model_type, :part_code, :created_at)
                """),
                {
                    "station": station,
                    "defect_type": defect_type,
                    "phenomenon": f"{station} 工位出现 {defect_type} 异常",
                    "root_cause": random.choice([
                        "相机曝光异常",
                        "PR规则未更新",
                        "模型版本不匹配",
                        "设备标定异常",
                        "网络上传失败",
                    ]),
                    "action": random.choice([
                        "更新规则配置",
                        "调整设备参数",
                        "重新采集样本",
                        "复核MES配置",
                        "执行设备点检",
                    ]),
                    "model_type": random.choice(["MEB", "CPA2", "MQB"]),
                    "part_code": random.choice(["WHEEL", "OCR", "TORQUE", "MIRROR"]),
                    "created_at": now - timedelta(days=random.randint(0, 90)),
                }
            )


def main():
    create_tables()
    ensure_default_admin()
    insert_sample_data()
    print("PostgreSQL 样例数据初始化完成")


if __name__ == "__main__":
    main()
