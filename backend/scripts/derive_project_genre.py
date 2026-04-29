import argparse
import asyncio
import json

from app.config import get_settings
from app.domain.models import Project
from app.infra.db import get_session_factory
from app.infra.volcano_client import get_volcano_client
from app.tasks.ai.parse_novel import normalize_parsed_genre
from app.utils.json_utils import extract_json


def _build_prompt(story: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "你是小说题材识别专家,只返回纯 JSON,不包含解释。"},
        {
            "role": "user",
            "content": (
                "请根据小说正文识别短题材标签,返回 JSON: {\"genre\":\"...\"}。\n"
                "genre 应是从正文内容得出的正向题材标签,例如 现代末世、都市悬疑、科幻悬疑、古风权谋。\n"
                "不要沿用已有项目字段,只依据正文判断。\n\n"
                f"小说正文:\n{story[:12000]}"
            ),
        },
    ]


async def derive_project_genre(project_id: str, dry_run: bool) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise SystemExit(f"project not found: {project_id}")

        settings = get_settings()
        client = get_volcano_client()
        resp = await client.chat_completions(
            model=settings.ark_chat_model,
            messages=_build_prompt(project.story or ""),
        )
        content = resp.choices[0].message.content
        data = extract_json(content)
        genre = normalize_parsed_genre(data.get("genre"))
        if not genre:
            raise SystemExit(f"model returned invalid genre: {json.dumps(data, ensure_ascii=False)}")

        print(json.dumps({"id": project.id, "old_genre": project.genre, "new_genre": genre}, ensure_ascii=False))
        if not dry_run:
            project.genre = genre
            await session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive and persist project genre from the novel text.")
    parser.add_argument("project_id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(derive_project_genre(args.project_id, args.dry_run))


if __name__ == "__main__":
    main()
