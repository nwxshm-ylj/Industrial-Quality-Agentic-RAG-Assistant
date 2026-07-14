from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage
else:
    BaseMessage = Any


@dataclass(frozen=True)
class PromptVariableSpec:
    required: bool = True
    sensitive: bool = False
    max_length: int | None = None


@dataclass(frozen=True)
class PromptMessageTemplate:
    role: str
    template: str


@dataclass(frozen=True)
class PromptDefinition:
    prompt_id: str
    version: str
    component: str
    description: str
    owner: str
    status: str
    messages: tuple[PromptMessageTemplate, ...]
    variables: dict[str, PromptVariableSpec]
    output_contract: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PromptReference:
    prompt_id: str
    version: str
    component: str
    release_id: str
    content_hash: str

    def to_metadata(self) -> dict[str, str]:
        return {
            "prompt_id": self.prompt_id,
            "prompt_version": self.version,
            "prompt_component": self.component,
            "prompt_release": self.release_id,
            "prompt_hash": self.content_hash,
        }


@dataclass(frozen=True)
class RenderedPrompt:
    messages: tuple[BaseMessage, ...]
    reference: PromptReference


@dataclass(frozen=True)
class PromptReleaseEntry:
    component: str
    file_path: str
    expected_hash: str
    definition: PromptDefinition
    reference: PromptReference
