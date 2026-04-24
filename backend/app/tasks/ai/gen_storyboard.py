import asyncio
import json
import logging
import re
from typing import Any

from app.infra.db import get_session_factory
from app.infra.volcano_client import get_volcano_client
from app.domain.models import Project, StoryboardShot
from app.pipeline import ProjectStageRaw, advance_stage, update_job_progress
from app.pipeline.storyboard_states import StoryboardStatus
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def build_segment_plan_prompt(story: str) -> str:
    return f"""你是短剧分镜策划师。请把小说拆成 8-12 个“视频片段级分镜”。

重要定义：
- 一个分镜不是单帧画面，而是一个 5-15 秒的视频片段。
- 每个视频片段可以包含多个子镜头，但本阶段只生成片段级描述，不展开子镜头。
- 每个片段必须对应小说中的一段明确剧情或氛围，不要凭空扩写。

输出要求：
只返回合法 JSON 数组，不要 Markdown，不要解释。

每个对象包含：
- idx: number，从 1 开始连续递增
- title: string，8-16 字
- description: string，片段级剧情描述，50-100 字
- duration_sec: number，只能是 5、8、10、12、15
- source_query: string，用于从小说中检索原文的关键词短句，必须包含角色/地点/事件关键词
- key_characters: string[]，本片段出现的角色名，没有则空数组
- key_scene: string，具体场景名
- narrative_purpose: string，本片段的叙事作用，例如“建立氛围”“推动冲突”“制造反转”“情绪收束”
- tags: string[]，3-6 个标签

规则：
1. 片段之间必须按小说剧情顺序排列。
2. 不要把整章剧情压成一个片段。
3. 每个片段只承担一个核心叙事目的。
4. 最后一个片段必须形成悬念、反转或情绪钩子。
5. 角色必须使用小说原名；没有名字时使用身份称呼。
6. 场景必须具体，例如“雨夜宫门”“东宫偏殿”，不要只写“室内”“皇宫”。

小说内容：
{story}"""


def build_expand_segment_prompt(segment: dict[str, Any], source_excerpt: str) -> str:
    segment_json = json.dumps(segment, ensure_ascii=False)
    return f"""你是短剧分镜导演和 AI 视频提示词工程师。请根据“片段级分镜描述”和“小说原文片段”，生成一个 5-15 秒视频片段的具体分镜。

重要定义：
- 输出的是一个视频片段，不是一张静态图。
- 一个视频片段内部可以包含 2-4 个子镜头 beat。
- 子镜头必须按时间顺序写入 detail。
- 不要改写剧情事实，不要加入原文没有支撑的重大事件。

只返回合法 JSON 对象，不要 Markdown，不要解释。

输出字段：
- idx: number，沿用输入 idx
- title: string，沿用或轻微优化输入 title
- description: string，50-120 字，描述整个视频片段发生了什么
- detail: string，80-220 字，必须使用时间戳子分镜格式
- duration_sec: number，沿用输入 duration_sec
- tags: string[]，3-6 个标签
- beats: array，2-4 个子镜头对象，每个对象包含 time、shot_type、camera_movement、action、visual

detail 格式要求：
- 开头写总时长和画幅，例如“8秒，9:16竖屏。”
- 必须包含 2-4 个时间段，例如“0-2s：...；2-5s：...；5-8s：...”
- 每个时间段必须包含：景别、角色/主体、动作、运镜、光影或氛围
- 必须至少出现一个景别：特写、近景、中景、全景、远景
- 必须至少出现一个运镜：固定机位、缓慢推进、横移跟拍、俯拍、仰拍、手持轻晃、由远推近
- 如果原文有雨、雾、火光、烛光、雷电、血迹、烟尘，必须写入 detail
- 不要写字幕、水印、旁白字段

片段级分镜：
{segment_json}

小说原文片段：
{source_excerpt}"""


def _tokens_for_match(segment: dict[str, Any]) -> list[str]:
    raw_parts: list[str] = [
        str(segment.get("source_query") or ""),
        str(segment.get("title") or ""),
        str(segment.get("key_scene") or ""),
    ]
    raw_parts.extend(str(item) for item in segment.get("key_characters") or [])
    raw_parts.extend(str(item) for item in segment.get("tags") or [])
    raw = " ".join(raw_parts)
    tokens = [t for t in re.split(r"[\s,，。；;、:：|/（）()]+", raw) if len(t) >= 2]
    return list(dict.fromkeys(tokens))


def match_source_excerpt(
    story: str,
    segment: dict[str, Any],
    *,
    window_chars: int = 600,
) -> tuple[str, dict[str, Any]]:
    if not story:
        return "", {"start": 0, "end": 0, "match_score": 0, "query": segment.get("source_query") or ""}

    tokens = _tokens_for_match(segment)
    paragraphs = [(match.start(), match.group(0)) for match in re.finditer(r"[^\n]+", story)]
    if paragraphs:
        best_start, best_paragraph = max(
            paragraphs,
            key=lambda item: sum(1 for token in tokens if token in item[1]),
        )
        best_score = sum(1 for token in tokens if token in best_paragraph)
        if best_score > 0:
            if len(best_paragraph) <= window_chars * 4:
                end = best_start + len(best_paragraph)
                anchor = {
                    "start": best_start,
                    "end": end,
                    "match_score": round(best_score / max(1, len(tokens)), 3),
                    "query": segment.get("source_query") or "",
                }
                return best_paragraph.strip(), anchor

    best_start = 0
    best_score = -1
    stride = max(1, window_chars // 2)
    for start in range(0, len(story), stride):
        window = story[start : start + window_chars]
        score = sum(1 for token in tokens if token in window)
        if score > best_score:
            best_score = score
            best_start = start

    end = min(len(story), best_start + window_chars)
    excerpt = story[best_start:end].strip()
    max_score = max(1, len(tokens))
    anchor = {
        "start": best_start,
        "end": end,
        "match_score": round(max(0, best_score) / max_score, 3),
        "query": segment.get("source_query") or "",
    }
    return excerpt, anchor


def _duration(value: Any, default: int = 8) -> int:
    allowed = {5, 8, 10, 12, 15}
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return default
    return parsed if parsed in allowed else default


def normalize_expanded_storyboard(
    segment: dict[str, Any],
    expanded: dict[str, Any],
    source_excerpt: str,
    source_anchor: dict[str, Any],
) -> dict[str, Any]:
    beats = expanded.get("beats")
    if not isinstance(beats, list) or len(beats) < 2:
        raise ValueError("expanded storyboard beats must contain at least 2 items")

    tags = expanded.get("tags") if isinstance(expanded.get("tags"), list) else segment.get("tags")
    return {
        "idx": int(expanded.get("idx") or segment.get("idx") or 1),
        "title": str(expanded.get("title") or segment.get("title") or "未命名分镜")[:128],
        "description": str(expanded.get("description") or segment.get("description") or ""),
        "detail": str(expanded.get("detail") or ""),
        "duration_sec": _duration(expanded.get("duration_sec") or segment.get("duration_sec")),
        "tags": tags or [],
        "source_excerpt": source_excerpt,
        "source_anchor": source_anchor,
        "beats": beats,
    }


def _storyboards_from_json(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        for key in ("storyboards", "segments", "shots"):
            if isinstance(data.get(key), list):
                return data[key]
    return data if isinstance(data, list) else []


async def _chat_json(client, model: str, messages: list[dict[str, str]]) -> Any:
    from app.utils.json_utils import extract_json

    resp = await client.chat_completions(model=model, messages=messages)
    return extract_json(resp.choices[0].message.content)

async def _gen_storyboard_task(project_id: str, job_id: str):
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            # 1. 更新 Job 状态为 running
            await update_job_progress(session, job_id, status="running", progress=10, done=0, total=4)
            await session.commit()

            # 2. 获取项目信息
            project = await session.get(Project, project_id)
            if not project:
                logger.error(f"Project {project_id} not found")
                await update_job_progress(session, job_id, status="failed", error_msg="Project not found")
                await session.commit()
                return

            # 3. 调用 AI 生成片段级分镜
            client = get_volcano_client()
            from app.config import get_settings
            settings = get_settings()
            data = await _chat_json(
                client,
                settings.ark_chat_model,
                [
                    {"role": "system", "content": "你是短剧分镜策划师，只返回纯 JSON，不包含任何解释。"},
                    {"role": "user", "content": build_segment_plan_prompt(project.story)},
                ],
            )
            segments = _storyboards_from_json(data)
            if not segments:
                raise ValueError("未生成分镜片段")
            total_steps = len(segments) + 3
            await update_job_progress(session, job_id, progress=25, done=1, total=total_steps)
            await session.commit()

            # 4. 依据片段描述定位原文，再逐片段扩写成子分镜
            source_pairs = [match_source_excerpt(project.story, segment) for segment in segments]
            await update_job_progress(session, job_id, progress=35, done=2, total=total_steps)
            await session.commit()

            storyboards_data: list[dict[str, Any]] = []
            for index, (segment, (source_excerpt, source_anchor)) in enumerate(
                zip(segments, source_pairs, strict=False),
                start=1,
            ):
                expanded_data = await _chat_json(
                    client,
                    settings.ark_chat_model,
                    [
                        {"role": "system", "content": "你是短剧分镜导演，只返回纯 JSON 对象，不包含任何解释。"},
                        {"role": "user", "content": build_expand_segment_prompt(segment, source_excerpt)},
                    ],
                )
                if not isinstance(expanded_data, dict):
                    raise ValueError("具体分镜扩写必须返回 JSON 对象")
                storyboards_data.append(
                    normalize_expanded_storyboard(segment, expanded_data, source_excerpt, source_anchor)
                )
                progress = 35 + int(55 * index / len(segments))
                await update_job_progress(session, job_id, progress=progress, done=index + 2, total=total_steps)
                await session.commit()

            # 5. 批量插入分镜
            # 先清理已有的分镜(如果是重跑的话,但 M2 暂不考虑复杂重跑逻辑)
            # 在 M2 计划中,gen_storyboard 是从 draft 迁移到 storyboard_ready
            
            for item in storyboards_data:
                shot = StoryboardShot(
                    project_id=project_id,
                    idx=item["idx"],
                    title=item["title"],
                    description=item["description"],
                    detail=item.get("detail", ""),
                    duration_sec=item.get("duration_sec", 5.0),
                    tags=item.get("tags", []),
                    source_excerpt=item.get("source_excerpt"),
                    source_anchor=item.get("source_anchor"),
                    beats=item.get("beats"),
                    status=StoryboardStatus.PENDING.value
                )
                session.add(shot)
            
            await update_job_progress(session, job_id, progress=95, done=total_steps - 1, total=total_steps)
            # 6. 推进阶段
            await advance_stage(session, project, ProjectStageRaw.STORYBOARD_READY)
            
            # 7. 更新 Job 为成功
            await update_job_progress(session, job_id, status="succeeded", progress=100, done=total_steps, total=total_steps)
            await session.commit()
            
            logger.info(f"Project {project_id} storyboards generated successfully, advanced to storyboard_ready")
            
        except Exception as e:
            logger.exception(f"Error in gen_storyboard_task: {e}")
            await update_job_progress(session, job_id, status="failed", error_msg=str(e))
            await session.commit()

@celery_app.task(name="ai.gen_storyboard")
def gen_storyboard(project_id: str, job_id: str):
    asyncio.run(_gen_storyboard_task(project_id, job_id))
