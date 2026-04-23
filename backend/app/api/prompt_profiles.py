from sqlalchemy import func, select
from typing import Literal

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.envelope import Envelope
from app.api.errors import ApiError
from app.deps import get_db
from app.domain.models import Job, Project
from app.domain.schemas.prompt_profile import PromptProfileDraftUpdate, PromptProfileState
from app.domain.schemas.character import GenerateJobAck
from app.domain.services.prompt_profile_service import PromptProfileService
from app.pipeline.transitions import InvalidTransition, assert_asset_editable, update_job_progress
from app.tasks.ai.gen_character_prompt_profile import gen_character_prompt_profile
from app.tasks.ai.gen_scene_prompt_profile import gen_scene_prompt_profile
from app.tasks.ai.regen_character_assets_batch import regen_character_assets_batch
from app.tasks.ai.regen_scene_assets_batch import regen_scene_assets_batch

router = APIRouter(prefix="/projects/{project_id}/prompt-profiles", tags=["prompt-profiles"])


def _validate_kind(kind: str) -> Literal["character", "scene"]:
    if kind not in ("character", "scene"):
        raise ApiError(40001, f"非法 kind: {kind}", http_status=422)
    return kind


def _assert_profile_editable(project: Project, kind: Literal["character", "scene"]) -> None:
    try:
        assert_asset_editable(project, kind)
    except InvalidTransition as exc:
        raise ApiError(40301, str(exc), http_status=403) from exc


async def _get_project_or_404(db: AsyncSession, project_id: str) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise ApiError(40401, "项目不存在", http_status=404)
    return project


async def _assert_profile_editable_and_not_running(
    db: AsyncSession,
    project: Project,
    kind: Literal["character", "scene"],
    *,
    check_profile_job: bool,
    check_asset_job: bool,
) -> None:
    _assert_profile_editable(project, kind)

    kinds: list[str] = []
    if check_profile_job:
        kinds.append(f"gen_{kind}_prompt_profile")
    if check_asset_job:
        if kind == "character":
            kinds.extend(["extract_characters", "gen_character_asset", "regen_character_assets_batch"])
        else:
            kinds.extend(["gen_scene_asset", "regen_scene_assets_batch"])

    if not kinds:
        return

    running_stmt = select(Job).where(
        Job.project_id == project.id,
        Job.kind.in_(kinds),
        Job.status.in_(["queued", "running"]),
    )
    existing = (await db.execute(running_stmt)).scalars().first()
    if existing:
        raise ApiError(40901, "已有同类生成任务进行中", http_status=409)


@router.patch("/{kind}", response_model=Envelope[PromptProfileState])
async def patch_prompt_profile(
    payload: PromptProfileDraftUpdate,
    project_id: str = Path(..., description="项目 ID"),
    kind: str = Path(..., description="profile kind"),
    db: AsyncSession = Depends(get_db),
):
    valid_kind = _validate_kind(kind)
    project = await _get_project_or_404(db, project_id)
    _assert_profile_editable(project, valid_kind)

    state = PromptProfileService(db).update_draft(project, valid_kind, payload.prompt)
    await db.commit()
    return Envelope.success(state)


@router.delete("/{kind}/draft", response_model=Envelope[PromptProfileState])
async def clear_prompt_profile_draft(
    project_id: str = Path(..., description="项目 ID"),
    kind: str = Path(..., description="profile kind"),
    db: AsyncSession = Depends(get_db),
):
    valid_kind = _validate_kind(kind)
    project = await _get_project_or_404(db, project_id)
    _assert_profile_editable(project, valid_kind)

    state = PromptProfileService(db).clear_draft(project, valid_kind)
    await db.commit()
    return Envelope.success(state)


@router.post("/{kind}/generate", response_model=Envelope[GenerateJobAck])
async def generate_prompt_profile(
    project_id: str = Path(..., description="项目 ID"),
    kind: str = Path(..., description="profile kind"),
    db: AsyncSession = Depends(get_db),
):
    valid_kind = _validate_kind(kind)
    stmt = select(Project).where(Project.id == project_id).with_for_update()
    project = (await db.execute(stmt)).scalar_one_or_none()
    if project is None:
        raise ApiError(40401, "项目不存在", http_status=404)

    await _assert_profile_editable_and_not_running(
        db,
        project,
        valid_kind,
        check_profile_job=True,
        check_asset_job=True,
    )

    job = Job(
        project_id=project_id,
        kind=f"gen_{valid_kind}_prompt_profile",
        status="queued",
        progress=0,
        done=0,
        total=None,
    )
    db.add(job)
    await db.commit()

    try:
        if valid_kind == "character":
            gen_character_prompt_profile.delay(project_id, job.id)
        else:
            gen_scene_prompt_profile.delay(project_id, job.id)
    except Exception as exc:
        await update_job_progress(
            db,
            job.id,
            status="failed",
            error_msg=f"dispatch failed: {exc}",
        )
        await db.commit()
        raise

    return Envelope.success(GenerateJobAck(job_id=job.id, sub_job_ids=[]))


async def _finish_noop_job(
    db: AsyncSession,
    job: Job,
    skipped_locked_count: int,
) -> GenerateJobAck:
    job.result = {"skipped_locked_count": int(skipped_locked_count)}
    await update_job_progress(db, job.id, status="running", progress=10)
    await update_job_progress(db, job.id, status="succeeded", total=0, done=0, progress=100)
    await db.commit()
    return GenerateJobAck(job_id=job.id, sub_job_ids=[])


@router.post("/{kind}/confirm", response_model=Envelope[GenerateJobAck])
async def confirm_prompt_profile(
    project_id: str = Path(..., description="项目 ID"),
    kind: str = Path(..., description="profile kind"),
    db: AsyncSession = Depends(get_db),
):
    valid_kind = _validate_kind(kind)
    stmt = select(Project).where(Project.id == project_id).with_for_update()
    project = (await db.execute(stmt)).scalar_one_or_none()
    if project is None:
        raise ApiError(40401, "项目不存在", http_status=404)

    await _assert_profile_editable_and_not_running(
        db,
        project,
        valid_kind,
        check_profile_job=False,
        check_asset_job=True,
    )

    draft = (
        project.character_prompt_profile_draft
        if valid_kind == "character"
        else project.scene_prompt_profile_draft
    )
    if not draft or not draft.get("prompt"):
        raise ApiError(40001, "请先生成或填写草稿", http_status=422)

    if valid_kind == "character":
        from app.domain.models import Character
        from app.tasks.ai.extract_characters import extract_characters

        current_count = (
            await db.execute(select(func.count(Character.id)).where(Character.project_id == project_id))
        ).scalar() or 0
        unlocked_count = (
            await db.execute(
                select(func.count(Character.id)).where(
                    Character.project_id == project_id,
                    Character.locked.is_(False),
                )
            )
        ).scalar() or 0
        locked_count = (
            await db.execute(
                select(func.count(Character.id)).where(
                    Character.project_id == project_id,
                    Character.locked.is_(True),
                )
            )
        ).scalar() or 0

        previous_applied = project.character_prompt_profile_applied
        project.character_prompt_profile_applied = draft
        next_kind = "regen_character_assets_batch" if current_count > 0 else "extract_characters"
        job = Job(project_id=project_id, kind=next_kind, status="queued", progress=0, done=0, total=None)
        db.add(job)
        await db.commit()

        if current_count > 0 and unlocked_count == 0:
            return Envelope.success(await _finish_noop_job(db, job, int(locked_count)))

        try:
            if next_kind == "regen_character_assets_batch":
                regen_character_assets_batch.delay(project_id, job.id)
            else:
                extract_characters.delay(project_id, job.id)
        except Exception as exc:
            stmt = select(Project).where(Project.id == project_id).with_for_update()
            locked_project = (await db.execute(stmt)).scalar_one()
            locked_project.character_prompt_profile_applied = previous_applied
            await update_job_progress(db, job.id, status="failed", error_msg=f"dispatch failed: {exc}")
            await db.commit()
            raise
        return Envelope.success(GenerateJobAck(job_id=job.id, sub_job_ids=[]))

    from app.domain.models import Scene
    from app.tasks.ai.extract_scenes import extract_scenes

    current_count = (
        await db.execute(select(func.count(Scene.id)).where(Scene.project_id == project_id))
    ).scalar() or 0
    unlocked_count = (
        await db.execute(
            select(func.count(Scene.id)).where(
                Scene.project_id == project_id,
                Scene.locked.is_(False),
            )
        )
    ).scalar() or 0
    locked_count = (
        await db.execute(
            select(func.count(Scene.id)).where(
                Scene.project_id == project_id,
                Scene.locked.is_(True),
            )
        )
    ).scalar() or 0

    previous_applied = project.scene_prompt_profile_applied
    project.scene_prompt_profile_applied = draft
    next_kind = "regen_scene_assets_batch" if current_count > 0 else "gen_scene_asset"
    job = Job(project_id=project_id, kind=next_kind, status="queued", progress=0, done=0, total=None)
    db.add(job)
    await db.commit()

    if current_count > 0 and unlocked_count == 0:
        return Envelope.success(await _finish_noop_job(db, job, int(locked_count)))

    try:
        if next_kind == "regen_scene_assets_batch":
            regen_scene_assets_batch.delay(project_id, job.id)
        else:
            extract_scenes.delay(job.id, project_id)
    except Exception as exc:
        stmt = select(Project).where(Project.id == project_id).with_for_update()
        locked_project = (await db.execute(stmt)).scalar_one()
        locked_project.scene_prompt_profile_applied = previous_applied
        await update_job_progress(db, job.id, status="failed", error_msg=f"dispatch failed: {exc}")
        await db.commit()
        raise

    return Envelope.success(GenerateJobAck(job_id=job.id, sub_job_ids=[]))
