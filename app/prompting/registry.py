from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
from time import perf_counter
from typing import Any

import yaml

from app.core.metrics import record_prompt_render
from app.prompting.exceptions import PromptConfigurationError, PromptNotFoundError
from app.prompting.models import (
    PromptDefinition,
    PromptMessageTemplate,
    PromptReference,
    PromptReleaseEntry,
    PromptVariableSpec,
    RenderedPrompt,
)
from app.prompting.renderer import StrictPromptRenderer


_SEMVER_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_VALID_STATUSES = {"draft", "candidate", "active", "deprecated"}


class PromptRegistry:
    """加载一个不可变 Prompt Release，并为运行时提供严格渲染。"""

    def __init__(
        self,
        *,
        catalog_path: str | Path,
        release_path: str | Path,
        renderer: StrictPromptRenderer | None = None,
    ) -> None:
        self.catalog_path = Path(catalog_path).resolve()
        self.release_path = Path(release_path).resolve()
        self.renderer = renderer or StrictPromptRenderer()
        self.release_id = ""
        self.channel = ""
        self._entries: dict[str, PromptReleaseEntry] = {}
        self._load()

    def render(
        self,
        component: str,
        variables: dict[str, Any],
    ) -> RenderedPrompt:
        entry = self._entries.get(component)
        if entry is None:
            raise PromptNotFoundError(
                f"活动 Prompt Release 中不存在组件: {component}"
            )
        started_at = perf_counter()
        try:
            rendered = self.renderer.render(
                entry.definition,
                entry.reference,
                variables,
            )
        except Exception:
            record_prompt_render(
                prompt_id=entry.reference.prompt_id,
                prompt_version=entry.reference.version,
                component=component,
                status="failed",
                latency_ms=(perf_counter() - started_at) * 1000,
            )
            raise
        record_prompt_render(
            prompt_id=entry.reference.prompt_id,
            prompt_version=entry.reference.version,
            component=component,
            status="success",
            latency_ms=(perf_counter() - started_at) * 1000,
        )
        return rendered

    def release_metadata(self) -> dict[str, Any]:
        return {
            "release_id": self.release_id,
            "channel": self.channel,
            "versions": {
                component: entry.reference.version
                for component, entry in sorted(self._entries.items())
            },
        }

    def references(self) -> dict[str, PromptReference]:
        return {
            component: entry.reference
            for component, entry in self._entries.items()
        }

    def _load(self) -> None:
        if not self.catalog_path.is_dir():
            raise PromptConfigurationError(
                f"Prompt Catalog 目录不存在: {self.catalog_path}"
            )
        release = self._load_yaml(self.release_path)
        self.release_id = self._required_string(release, "release_id")
        self.channel = self._required_string(release, "channel")
        prompt_entries = release.get("prompts")
        if not isinstance(prompt_entries, dict) or not prompt_entries:
            raise PromptConfigurationError("Prompt Release 必须包含非空 prompts 映射")

        for component, raw_entry in prompt_entries.items():
            if not isinstance(component, str) or not isinstance(raw_entry, dict):
                raise PromptConfigurationError("Prompt Release 条目格式不合法")
            entry = self._load_entry(component, raw_entry)
            if component in self._entries:
                raise PromptConfigurationError(f"Prompt 组件重复: {component}")
            self._entries[component] = entry

    def _load_entry(
        self,
        component: str,
        raw_entry: dict[str, Any],
    ) -> PromptReleaseEntry:
        file_path = self._required_string(raw_entry, "file")
        expected_hash = self._required_string(raw_entry, "sha256").lower()
        if not _HASH_PATTERN.fullmatch(expected_hash):
            raise PromptConfigurationError(
                f"Prompt {component} 的 sha256 必须是 64 位小写十六进制"
            )

        resolved_file = (self.catalog_path / file_path).resolve()
        try:
            resolved_file.relative_to(self.catalog_path)
        except ValueError as exc:
            raise PromptConfigurationError(
                f"Prompt 文件越过 Catalog 目录: {file_path}"
            ) from exc
        if not resolved_file.is_file():
            raise PromptConfigurationError(f"Prompt 文件不存在: {resolved_file}")

        try:
            prompt_text = resolved_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise PromptConfigurationError(
                f"Prompt 文件读取失败: {resolved_file}: {exc}"
            ) from exc
        canonical_bytes = prompt_text.replace("\r\n", "\n").replace(
            "\r", "\n"
        ).encode("utf-8")
        actual_hash = sha256(canonical_bytes).hexdigest()
        if actual_hash != expected_hash:
            raise PromptConfigurationError(
                f"Prompt {component} 内容哈希不一致: expected={expected_hash}, "
                f"actual={actual_hash}"
            )

        definition = self._parse_definition(self._load_yaml(resolved_file))
        if definition.component != component:
            raise PromptConfigurationError(
                f"Prompt 组件不一致: manifest={component}, "
                f"definition={definition.component}"
            )

        manifest_id = self._required_string(raw_entry, "id")
        manifest_version = self._required_string(raw_entry, "version")
        if definition.prompt_id != manifest_id:
            raise PromptConfigurationError(
                f"Prompt ID 不一致: manifest={manifest_id}, "
                f"definition={definition.prompt_id}"
            )
        if definition.version != manifest_version:
            raise PromptConfigurationError(
                f"Prompt 版本不一致: manifest={manifest_version}, "
                f"definition={definition.version}"
            )

        reference = PromptReference(
            prompt_id=definition.prompt_id,
            version=definition.version,
            component=definition.component,
            release_id=self.release_id,
            content_hash=actual_hash,
        )
        return PromptReleaseEntry(
            component=component,
            file_path=file_path,
            expected_hash=expected_hash,
            definition=definition,
            reference=reference,
        )

    def _parse_definition(self, raw: dict[str, Any]) -> PromptDefinition:
        prompt_id = self._required_string(raw, "id")
        version = self._required_string(raw, "version")
        if not _SEMVER_PATTERN.fullmatch(version):
            raise PromptConfigurationError(
                f"Prompt {prompt_id} 版本不是合法 SemVer: {version}"
            )
        status = self._required_string(raw, "status")
        if status not in _VALID_STATUSES:
            raise PromptConfigurationError(
                f"Prompt {prompt_id} 状态不合法: {status}"
            )

        raw_messages = raw.get("messages")
        if not isinstance(raw_messages, list) or not raw_messages:
            raise PromptConfigurationError(f"Prompt {prompt_id} 缺少 messages")
        messages = []
        for item in raw_messages:
            if not isinstance(item, dict):
                raise PromptConfigurationError(
                    f"Prompt {prompt_id} 的 message 格式不合法"
                )
            messages.append(
                PromptMessageTemplate(
                    role=self._required_string(item, "role"),
                    template=self._required_string(item, "template"),
                )
            )

        raw_variables = raw.get("variables", {})
        if not isinstance(raw_variables, dict):
            raise PromptConfigurationError(
                f"Prompt {prompt_id} 的 variables 必须是映射"
            )
        variables: dict[str, PromptVariableSpec] = {}
        for name, item in raw_variables.items():
            if not isinstance(name, str) or not isinstance(item, dict):
                raise PromptConfigurationError(
                    f"Prompt {prompt_id} 的变量声明不合法"
                )
            max_length = item.get("max_length")
            if max_length is not None:
                if not isinstance(max_length, int) or max_length < 1:
                    raise PromptConfigurationError(
                        f"Prompt 变量 {name} 的 max_length 必须是正整数"
                    )
            variables[name] = PromptVariableSpec(
                required=bool(item.get("required", True)),
                sensitive=bool(item.get("sensitive", False)),
                max_length=max_length,
            )

        output_contract = raw.get("output_contract", {})
        if not isinstance(output_contract, dict):
            raise PromptConfigurationError(
                f"Prompt {prompt_id} 的 output_contract 必须是映射"
            )

        return PromptDefinition(
            prompt_id=prompt_id,
            version=version,
            component=self._required_string(raw, "component"),
            description=self._required_string(raw, "description"),
            owner=self._required_string(raw, "owner"),
            status=status,
            messages=tuple(messages),
            variables=variables,
            output_contract=output_contract,
        )

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise PromptConfigurationError(f"Prompt 配置文件不存在: {path}")
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise PromptConfigurationError(
                f"Prompt YAML 读取失败: {path}: {exc}"
            ) from exc
        if not isinstance(loaded, dict):
            raise PromptConfigurationError(f"Prompt YAML 根节点必须是映射: {path}")
        return loaded

    @staticmethod
    def _required_string(mapping: dict[str, Any], key: str) -> str:
        value = mapping.get(key)
        if not isinstance(value, str) or not value.strip():
            raise PromptConfigurationError(f"Prompt 配置缺少字符串字段: {key}")
        return value.strip()
