from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

from app.domain.models import Character, Scene, StoryboardShot


CHARACTER_REFERENCE_KINDS = {"character", "character_headshot"}


def build_reference_candidates(
    shot: StoryboardShot,
    scenes: Sequence[Scene],
    characters: Sequence[Character],
    asset_ref: Callable[[str | None], str | None],
) -> list[dict]:
    shot_text = _compose_text(shot.title, shot.description, shot.detail, " ".join(shot.tags or []))
    shot_terms = _text_terms(shot_text)

    ordered_scenes = sorted(
        [scene for scene in scenes if asset_ref(scene.reference_image_url)],
        key=lambda scene: _scene_sort_key(shot, shot_text, shot_terms, scene),
        reverse=True,
    )
    ordered_characters = sorted(
        [
            character
            for character in characters
            if asset_ref(character.full_body_image_url or character.reference_image_url) or asset_ref(character.headshot_image_url)
        ],
        key=lambda character: _character_sort_key(shot_text, shot_terms, character),
        reverse=True,
    )
    items = [
        *[
            {
                "id": f"scene:{scene.id}",
                "kind": "scene",
                "source_id": scene.id,
                "name": scene.name,
                "alias": scene.name,
                "mention_key": f"scene:{scene.id}",
                "image_url": asset_ref(scene.reference_image_url),
                "origin": "auto",
                "reason": _scene_reason(shot, shot_text, shot_terms, scene),
            }
            for scene in ordered_scenes
        ],
    ]
    for character in ordered_characters:
        full_body_key = character.full_body_image_url or character.reference_image_url
        if asset_ref(full_body_key):
            items.append(
                {
                    "id": f"character:{character.id}",
                    "kind": "character",
                    "source_id": character.id,
                    "name": character.name,
                    "alias": f"{character.name}-全身",
                    "mention_key": f"character:{character.id}",
                    "image_url": asset_ref(full_body_key),
                    "origin": "auto",
                    "reason": _character_reason(shot_text, shot_terms, character),
                }
            )
        if asset_ref(character.headshot_image_url):
            items.append(
                {
                    "id": f"character_headshot:{character.id}",
                    "kind": "character_headshot",
                    "source_id": character.id,
                    "name": character.name,
                    "alias": f"{character.name}-头像",
                    "mention_key": f"character_headshot:{character.id}",
                    "image_url": asset_ref(character.headshot_image_url),
                    "origin": "auto",
                    "reason": "角色白底头像参考图",
                }
            )
    return items


def default_selected_references(candidates: list[dict]) -> list[dict]:
    scenes = [item for item in candidates if item.get("kind") == "scene"]
    characters = [item for item in candidates if item.get("kind") in CHARACTER_REFERENCE_KINDS]
    return [*scenes[:1], *characters[:2]]


def selected_references_from_ids(candidates: list[dict], raw_ids: object) -> list[dict]:
    candidate_map = {item["id"]: item for item in candidates}
    selected: list[dict] = []
    selected_kinds = {"scene": 0, "character": 0}

    if isinstance(raw_ids, list):
        for item in raw_ids:
            ref_id = str(item).strip()
            candidate = candidate_map.get(ref_id)
            if not candidate or candidate in selected:
                continue

            kind = str(candidate.get("kind"))
            lane = "character" if kind in CHARACTER_REFERENCE_KINDS else kind
            if lane == "scene" and selected_kinds["scene"] >= 1:
                continue
            if lane == "character" and selected_kinds["character"] >= 2:
                continue

            selected.append(candidate)
            if lane in selected_kinds:
                selected_kinds[lane] += 1
    return selected


def _scene_sort_key(
    shot: StoryboardShot,
    shot_text: str,
    shot_terms: set[str],
    scene: Scene,
) -> tuple[int, int, float]:
    return (
        _scene_match_score(shot, shot_text, shot_terms, scene),
        1 if scene.id == shot.scene_id else 0,
        _timestamp(scene.updated_at),
    )


def _character_sort_key(
    shot_text: str,
    shot_terms: set[str],
    character: Character,
) -> tuple[int, float]:
    return (
        _character_match_score(shot_text, shot_terms, character),
        -_timestamp(character.created_at),
    )


def _scene_reason(
    shot: StoryboardShot,
    shot_text: str,
    shot_terms: set[str],
    scene: Scene,
) -> str:
    if scene.id == shot.scene_id:
        return "镜头已绑定该场景"
    if _scene_match_score(shot, shot_text, shot_terms, scene) > 0:
        return "镜头文案命中该场景"
    return "无人场景参考图，供模型按镜头内容筛选"


def _character_reason(shot_text: str, shot_terms: set[str], character: Character) -> str:
    if character.name and character.name in shot_text:
        return "镜头文案直接提到该人物"
    if _character_match_score(shot_text, shot_terms, character) > 0:
        return "镜头文案命中该人物"
    return "项目候选人物，供模型按镜头内容筛选"


def _scene_match_score(
    shot: StoryboardShot,
    shot_text: str,
    shot_terms: set[str],
    scene: Scene,
) -> int:
    score = 0
    if scene.id == shot.scene_id:
        score += 10_000

    scene_text = _compose_text(scene.name, scene.theme, scene.summary, scene.description)
    scene_terms = _text_terms(scene_text)
    score += _overlap_score(shot_terms, scene_terms)
    score += _phrase_bonus(shot_text, [scene.name, scene.theme, scene.summary, scene.description])
    return score


def _character_match_score(shot_text: str, shot_terms: set[str], character: Character) -> int:
    score = 0
    if character.name and character.name in shot_text:
        score += 10_000

    character_text = _compose_text(character.name, character.summary, character.description)
    character_terms = _text_terms(character_text)
    score += _overlap_score(shot_terms, character_terms)
    score += _phrase_bonus(shot_text, [character.name, character.summary, character.description])
    return score


def _phrase_bonus(haystack: str, phrases: list[str | None]) -> int:
    bonus = 0
    for phrase in phrases:
        if not phrase:
            continue
        compact = _normalize_text(phrase).replace(" ", "")
        if len(compact) >= 2 and compact in haystack:
            bonus += len(compact) * 50
    return bonus


def _overlap_score(left: set[str], right: set[str]) -> int:
    return sum(len(token) * len(token) for token in left & right)


def _text_terms(text: str) -> set[str]:
    normalized = _normalize_text(text)
    compact = normalized.replace(" ", "")
    terms = {token for token in normalized.split() if len(token) >= 2}

    for size in (2, 3, 4):
        for index in range(max(len(compact) - size + 1, 0)):
            token = compact[index : index + size]
            if len(token) == size and not token.isdigit():
                terms.add(token)
    return terms


def _normalize_text(text: str) -> str:
    normalized: list[str] = []
    for char in text.lower():
        if char.isalnum() or _is_cjk(char):
            normalized.append(char)
        else:
            normalized.append(" ")
    return " ".join("".join(normalized).split())


def _compose_text(*parts: str | None) -> str:
    return _normalize_text(" ".join(part for part in parts if part))


def _timestamp(value: datetime | None) -> float:
    return value.timestamp() if value else 0.0


def _is_cjk(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff"
