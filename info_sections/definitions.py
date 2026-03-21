"""JSON-serializable shapes for infobox sections (transport + client renderers)."""

from __future__ import annotations

from typing import Any, Optional, TypedDict


class MandarinReadingRow(TypedDict):
    pinyin_accent: str
    tone_color: str
    definitions: list[str]


class MandarinDefinitionsData(TypedDict):
    readings: list[MandarinReadingRow]


class ToneSegment(TypedDict):
    text: str
    tone: str


class CantoneseReadingsData(TypedDict):
    segments: list[ToneSegment]


class PlainReadingData(TypedDict):
    text: str


class JoinedReadingsData(TypedDict):
    items: list[str]


class MessageData(TypedDict, total=False):
    text: str
    kind: str


SectionPayload = (
    MandarinDefinitionsData
    | CantoneseReadingsData
    | PlainReadingData
    | JoinedReadingsData
    | MessageData
    | dict[str, Any]
)


class SectionJson(TypedDict):
    id: str
    type: str
    title: str
    data: Optional[SectionPayload]
    error: Optional[str]


class SectionGroupJson(TypedDict):
    id: str
    label: str
    sections: list[dict[str, Any]]


class InfoSectionOptionsResponse(TypedDict):
    groups: list[SectionGroupJson]


class CharacterInfoMeta(TypedDict):
    character: str
    error: Optional[str]


class CharacterInfoResponse(TypedDict):
    sections: list[SectionJson]
    meta: CharacterInfoMeta
