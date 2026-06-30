from datetime import datetime, timedelta
import random

from sqlalchemy import text

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
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );

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
    """

    with engine.begin() as conn:
        conn.execute(text(ddl))


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
    insert_sample_data()
    print("PostgreSQL 样例数据初始化完成")


if __name__ == "__main__":
    main()