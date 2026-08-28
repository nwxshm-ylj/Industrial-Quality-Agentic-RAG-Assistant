from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable


ENTITY_FIELDS = (
    "vehicle_models",
    "systems",
    "components",
    "processes",
    "stations",
    "failure_modes",
    "symptoms",
    "root_causes",
    "process_parameters",
    "control_measures",
    "corrective_actions",
)

ENTITY_LABELS = {
    "vehicle_models": "VehicleModel",
    "systems": "System",
    "components": "Component",
    "processes": "Process",
    "stations": "Station",
    "failure_modes": "FailureMode",
    "symptoms": "Symptom",
    "root_causes": "RootCause",
    "process_parameters": "ProcessParameter",
    "control_measures": "ControlMeasure",
    "corrective_actions": "CorrectiveAction",
}


class QualityEntityLinker:
    """Deterministic first-stage linker for manufacturing quality vocabulary.

    The rule set deliberately favors precision over recall. It supplies stable
    metadata and graph keys without calling an LLM, so ingestion and unit tests
    remain deterministic. The aliases can later be moved to a managed taxonomy.
    """

    _ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
        "systems": {
            "body": ("车身", "白车身", "body in white", "biw"),
            "chassis": ("底盘", "chassis"),
            "paint": ("油漆", "涂装", "paint"),
            "electrical": ("电气", "电器", "electrical"),
            "steering": ("转向系统", "steering"),
        },
        "components": {
            "fds_fastener": ("fds", "流钻螺钉", "热融自攻丝"),
            "wheel_house": ("轮罩", "wheel house", "wheelhouse"),
            "door_outer_panel": ("门外板", "车门外板", "door outer panel"),
            "wheel": ("轮毂", "车轮", "wheel"),
            "steering_gear": ("转向机", "steering gear"),
            "door": ("车门", "前门", "后门", "door"),
        },
        "processes": {
            "fastening": ("拧紧", "紧固", "打紧", "fastening"),
            "welding": ("焊接", "焊缝", "mig", "welding"),
            "painting": ("喷涂", "清漆", "漆膜", "painting", "coating"),
            "inspection": ("检验", "检查", "测量", "inspection"),
            "assembly": ("装配", "总装", "assembly"),
        },
        "failure_modes": {
            "loose": ("松动", "松脱", "loose"),
            "gap_excessive": ("缝隙大", "间隙大", "gap too large"),
            "weld_deviation": ("焊缝偏", "焊偏", "weld deviation"),
            "orange_peel": ("桔皮", "橘皮", "orange peel"),
            "leakage": ("漏水", "泄漏", "渗漏", "leak"),
            "mismatch": ("不一致", "错装", "错误", "mismatch"),
            "deformation": ("变形", "deformation"),
            "crack": ("开裂", "裂纹", "crack"),
            "surface_impression": ("表面压印", "压印", "surface impression"),
        },
        "symptoms": {
            "alarm": ("报警", "告警", "alarm"),
            "abnormal_noise": ("异响", "abnormal noise"),
            "visual_defect": ("外观缺陷", "表面缺陷", "visual defect"),
        },
        "root_causes": {
            "insufficient_torque": ("扭矩不足", "扭矩低", "低扭矩"),
            "dimensional_variation": ("尺寸波动", "尺寸偏差", "公差波动"),
            "parameter_setting": ("参数设置", "参数错误", "设定错误"),
            "inspection_escape": ("漏检", "检验遗漏", "inspection escape"),
        },
        "process_parameters": {
            "torque": ("扭矩", "torque"),
            "welding_trajectory": ("焊接轨迹", "焊枪轨迹", "welding trajectory"),
            "film_thickness": ("膜厚", "漆膜厚度", "film thickness"),
            "spray_flow": ("喷涂流量", "喷枪流量", "spray flow"),
            "voltage": ("电压", "voltage"),
        },
        "control_measures": {
            "visual_inspection": ("目视检查", "外观检查", "visual inspection"),
            "torque_monitoring": ("扭矩监控", "扭矩检测", "torque monitoring"),
            "dimensional_measurement": ("尺寸测量", "尺寸检测"),
        },
        "corrective_actions": {
            "parameter_adjustment": ("调整参数", "参数调整", "优化参数"),
            "recalibration": ("重新标定", "校准", "recalibration"),
            "rework": ("返工", "返修", "rework"),
        },
    }

    _STATION_PATTERN = re.compile(r"(?<![A-Za-z0-9])(?:ZP\d{1,2}|[A-Z]{2,12}\d{1,3})(?![A-Za-z0-9])", re.I)
    _VEHICLE_MODEL_PATTERN = re.compile(
        r"(?<![A-Za-z0-9])(?:LAMANDO\s*L|THARU|TIGUAN(?:\s*L)?|LAVIDA(?:\s*FL)?|MEB|MQB|ID\.?\s*\d)(?![A-Za-z0-9])",
        re.I,
    )

    def link(self, text: str) -> dict[str, list[dict[str, str]]]:
        normalized_text = (text or "").lower()
        matches: dict[str, list[dict[str, str]]] = defaultdict(list)

        for entity_type, canonical_values in self._ALIASES.items():
            for canonical, aliases in canonical_values.items():
                matched_alias = next(
                    (alias for alias in aliases if alias.lower() in normalized_text),
                    None,
                )
                if matched_alias:
                    matches[entity_type].append(
                        {
                            "canonical_key": canonical,
                            "name": matched_alias,
                        }
                    )

        self._append_pattern_matches(
            matches["stations"],
            self._STATION_PATTERN.findall(text or ""),
        )
        self._append_pattern_matches(
            matches["vehicle_models"],
            self._VEHICLE_MODEL_PATTERN.findall(text or ""),
        )

        return {
            field: _deduplicate(matches.get(field, []))
            for field in ENTITY_FIELDS
            if matches.get(field)
        }

    @staticmethod
    def flatten(entities: dict[str, list[dict[str, str]]]) -> dict[str, list[str]]:
        return {
            field: [item["canonical_key"] for item in values]
            for field, values in entities.items()
            if values
        }

    @staticmethod
    def search_terms(entities: dict[str, list[dict[str, str]]]) -> list[str]:
        return list(
            dict.fromkeys(
                value
                for values in entities.values()
                for item in values
                for value in (item["canonical_key"], item["name"])
                if value
            )
        )

    @staticmethod
    def graph_entities(
        entities: dict[str, list[dict[str, str]]],
    ) -> Iterable[dict[str, str]]:
        for field, values in entities.items():
            label = ENTITY_LABELS.get(field)
            if not label:
                continue
            for value in values:
                yield {
                    "entity_type": field,
                    "label": label,
                    "canonical_key": value["canonical_key"],
                    "name": value["name"],
                }

    @staticmethod
    def _append_pattern_matches(
        target: list[dict[str, str]],
        values: Iterable[str],
    ) -> None:
        for value in values:
            name = re.sub(r"\s+", " ", value.strip())
            if name:
                target.append(
                    {
                        "canonical_key": name.lower().replace(" ", "_"),
                        "name": name,
                    }
                )


def _deduplicate(values: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for value in values:
        key = value["canonical_key"]
        if key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output
