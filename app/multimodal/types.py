from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MultimodalEmbeddingInput:
    """SDK-independent representation accepted by multimodal backends."""

    text: str | None = None
    images: tuple[str, ...] = ()
    video: str | None = None

    def __post_init__(self) -> None:
        text = self.text.strip() if self.text else None
        images = tuple(image.strip() for image in self.images if image.strip())
        video = self.video.strip() if self.video else None
        if not text and not images and not video:
            raise ValueError("multimodal input must contain text, image, or video")
        if len(images) > 5:
            raise ValueError("qwen3-vl-embedding accepts at most 5 images")
        if 1 + len(images) + int(bool(video)) > 20:
            raise ValueError("multimodal input exceeds the 20-content limit")
        for image in images:
            if not image.startswith(("https://", "http://", "data:image/")):
                raise ValueError(
                    "image must be an HTTP(S) URL or Base64 data:image URI"
                )
        if video and not video.startswith(("https://", "http://")):
            raise ValueError("video must be a publicly accessible HTTP(S) URL")
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "images", images)
        object.__setattr__(self, "video", video)

    def to_api_contents(self) -> list[dict[str, str]]:
        contents: list[dict[str, str]] = []
        if self.text:
            contents.append({"text": self.text})
        contents.extend({"image": image} for image in self.images)
        if self.video:
            contents.append({"video": self.video})
        return contents

    @property
    def modalities(self) -> tuple[str, ...]:
        values = []
        if self.text:
            values.append("text")
        if self.images:
            values.append("image")
        if self.video:
            values.append("video")
        return tuple(values)
