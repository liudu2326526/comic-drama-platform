from __future__ import annotations

from app.domain.schemas.reference import ReferenceMention


def normalize_reference_mentions(raw: list[ReferenceMention] | None) -> list[dict]:
    if not raw:
        return []
    seen: set[str] = set()
    result: list[dict] = []
    for item in raw:
        mention_key = item.mention_key.strip()
        label = item.label.strip()
        if not mention_key or mention_key in seen:
            continue
        seen.add(mention_key)
        result.append({"mention_key": mention_key, "label": label or mention_key})
    return result


def build_reference_binding_text(mentions: list[dict]) -> str:
    if not mentions:
        return ""
    lines = ["参考图绑定关系:"]
    for item in mentions:
        lines.append(f"- @{item['label']} => {item['mention_key']}")
    return "\n".join(lines)


def append_reference_binding(prompt: str, binding_text: str | None) -> str:
    if not binding_text:
        return prompt
    return f"{prompt.rstrip()}\n\n{binding_text}"
