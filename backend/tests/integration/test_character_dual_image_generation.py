import pytest
from importlib import import_module

from app.domain.models import Character, Job, Project
from app.infra.volcano_errors import VolcanoContentFilterError
from app.tasks.ai.gen_character_asset import run_character_asset_generation


@pytest.mark.asyncio
async def test_character_asset_generation_writes_full_body_and_headshot(db_session, monkeypatch):
    project = Project(
        name="雨夜",
        story="story",
        ratio="9:16",
        stage="storyboard_ready",
        character_style_reference_image_url="projects/p/style/ref.png",
    )
    db_session.add(project)
    await db_session.flush()
    character = Character(project_id=project.id, name="秦昭", role_type="supporting", summary="少年天子")
    db_session.add(character)
    await db_session.flush()
    job = Job(project_id=project.id, kind="gen_character_asset_single", status="queued", target_type="character", target_id=character.id)
    db_session.add(job)
    await db_session.commit()
    calls: list[dict] = []

    class FakeImageClient:
        async def image_generations(self, model, prompt, **kwargs):
            calls.append({"model": model, "prompt": prompt, **kwargs})
            return {"data": [{"url": f"https://volcano.example/tmp-{len(calls)}.png"}]}

    video_calls: list[dict] = []

    class FakeVideoClient:
        async def video_generations_create(self, **kwargs):
            video_calls.append(kwargs)
            return {"id": "video-task-1"}

        async def video_generations_get(self, task_id):
            return {
                "id": task_id,
                "status": "succeeded",
                "content": {"video_url": "https://volcano.example/turnaround.mp4"},
            }

    async def fake_persist_generated_asset(*, url, project_id, kind, ext="png"):
        suffix = url.rsplit("/", 1)[-1].rsplit("-", 1)[-1]
        return f"projects/{project_id}/{kind}/{suffix}.{ext}" if "." not in suffix else f"projects/{project_id}/{kind}/{suffix}"

    task_module = import_module("app.tasks.ai.gen_character_asset")
    monkeypatch.setattr(task_module, "get_character_image_client", lambda: FakeImageClient())
    monkeypatch.setattr(task_module, "get_volcano_client", lambda: FakeVideoClient())
    monkeypatch.setattr(task_module, "persist_generated_asset", fake_persist_generated_asset)

    await run_character_asset_generation(character.id, job.id, session=db_session)

    await db_session.refresh(character)
    await db_session.refresh(job)
    assert character.full_body_image_url and "/character_full_body/" in character.full_body_image_url
    assert character.reference_image_url == character.full_body_image_url
    assert character.headshot_image_url and "/character_headshot/" in character.headshot_image_url
    assert character.turnaround_image_url and character.turnaround_image_url.endswith(".mp4")
    assert "全身参考图" in calls[0]["prompt"]
    assert "头像参考图" in calls[1]["prompt"]
    assert "参考图使用规则：只参考参考图片的画风和服装质感" in calls[0]["prompt"]
    assert "不得参考参考图片中的人脸、发型、体型、姿态、身份、背景或构图" in calls[0]["prompt"]
    assert "参考图使用规则：只参考参考图片的画风和服装质感" in calls[1]["prompt"]
    assert "不得参考参考图片中的人脸、发型、体型、姿态、身份、背景或构图" in calls[1]["prompt"]
    assert calls[0]["model"] == "gpt-image-2"
    assert calls[1]["model"] == "gpt-image-2"
    assert calls[0]["references"][0].endswith("/style/ref.png")
    assert "/character_full_body/" in calls[1]["references"][0]
    assert len(video_calls) == 1
    assert video_calls[0]["generate_audio"] is True
    assert video_calls[0]["duration"] == 8
    assert video_calls[0]["image_inputs"] == [
        {"role": "first_frame", "url": video_calls[0]["image_inputs"][0]["url"]},
        {"role": "last_frame", "url": video_calls[0]["image_inputs"][1]["url"]},
    ]
    assert "/character_full_body/" in video_calls[0]["image_inputs"][0]["url"]
    assert "/character_headshot/" in video_calls[0]["image_inputs"][1]["url"]
    assert "林川" not in video_calls[0]["prompt"]
    assert "秦昭" not in video_calls[0]["prompt"]
    assert job.status == "succeeded"


@pytest.mark.asyncio
async def test_crowd_group_generates_only_primary_reference(db_session, monkeypatch):
    project = Project(name="末世", story="story", ratio="9:16", stage="storyboard_ready")
    db_session.add(project)
    await db_session.flush()
    character = Character(
        project_id=project.id,
        name="普通民众",
        role_type="crowd",
        visual_type="crowd_group",
        is_humanoid=False,
        summary="城区普通居民群体",
        description="群体构成：不同年龄居民；整体服装/形态：日常服装；颜色倾向：灰蓝；数量密度：中等；行动姿态：惊慌后退；与场景关系：街道群体；唯一辨识点：应急手环",
    )
    db_session.add(character)
    await db_session.flush()
    job = Job(project_id=project.id, kind="gen_character_asset_single", status="queued", target_type="character", target_id=character.id)
    db_session.add(job)
    await db_session.commit()
    image_calls: list[dict] = []
    video_calls: list[dict] = []

    class FakeImageClient:
        async def image_generations(self, model, prompt, **kwargs):
            image_calls.append({"prompt": prompt, **kwargs})
            return {"data": [{"url": "https://volcano.example/crowd.png"}]}

    class FakeVideoClient:
        async def video_generations_create(self, **kwargs):
            video_calls.append(kwargs)
            return {"id": "unexpected"}

    async def fake_persist_generated_asset(*, url, project_id, kind, ext="png"):
        return f"projects/{project_id}/{kind}/crowd.{ext}"

    task_module = import_module("app.tasks.ai.gen_character_asset")
    monkeypatch.setattr(task_module, "get_character_image_client", lambda: FakeImageClient())
    monkeypatch.setattr(task_module, "get_volcano_client", lambda: FakeVideoClient())
    monkeypatch.setattr(task_module, "persist_generated_asset", fake_persist_generated_asset)

    await run_character_asset_generation(character.id, job.id, session=db_session)

    await db_session.refresh(character)
    await db_session.refresh(job)
    assert job.status == "succeeded"
    assert job.total == 1
    assert job.done == 1
    assert len(image_calls) == 1
    assert video_calls == []
    assert character.full_body_image_url is not None
    assert character.headshot_image_url is None
    assert character.turnaround_image_url is None


@pytest.mark.asyncio
async def test_anomaly_entity_generates_primary_secondary_and_motion_reference(db_session, monkeypatch):
    project = Project(name="末世", story="story", ratio="9:16", stage="storyboard_ready")
    db_session.add(project)
    await db_session.flush()
    character = Character(
        project_id=project.id,
        name="异常吞噬暗影",
        role_type="antagonist",
        visual_type="anomaly_entity",
        is_humanoid=False,
        summary="吞噬生命的异常存在",
        description="形态边界：无固定形态；材质/粒子质感：黑雾；颜色光效：黑紫；核心符号：旋涡空洞；变化规律：持续蠕动；空间影响：压暗周围光线；危险感：靠近即吞噬；唯一辨识点：紫色裂纹边缘",
    )
    db_session.add(character)
    await db_session.flush()
    job = Job(project_id=project.id, kind="gen_character_asset_single", status="queued", target_type="character", target_id=character.id)
    db_session.add(job)
    await db_session.commit()
    image_calls: list[dict] = []
    video_calls: list[dict] = []

    class FakeImageClient:
        async def image_generations(self, model, prompt, **kwargs):
            image_calls.append({"prompt": prompt, **kwargs})
            return {"data": [{"url": f"https://volcano.example/anomaly-{len(image_calls)}.png"}]}

    class FakeVideoClient:
        async def video_generations_create(self, **kwargs):
            video_calls.append(kwargs)
            return {"id": "video-task-1"}

        async def video_generations_get(self, task_id):
            return {"id": task_id, "status": "succeeded", "content": {"video_url": "https://volcano.example/anomaly.mp4"}}

    async def fake_persist_generated_asset(*, url, project_id, kind, ext="png"):
        return f"projects/{project_id}/{kind}/{url.rsplit('/', 1)[-1]}.{ext}"

    task_module = import_module("app.tasks.ai.gen_character_asset")
    monkeypatch.setattr(task_module, "get_character_image_client", lambda: FakeImageClient())
    monkeypatch.setattr(task_module, "get_volcano_client", lambda: FakeVideoClient())
    monkeypatch.setattr(task_module, "persist_generated_asset", fake_persist_generated_asset)

    await run_character_asset_generation(character.id, job.id, session=db_session)

    await db_session.refresh(character)
    await db_session.refresh(job)
    assert job.status == "succeeded"
    assert job.total == 3
    assert job.done == 3
    assert len(image_calls) == 2
    assert len(video_calls) == 1
    assert "动态特效参考视频" in video_calls[0]["prompt"]
    assert video_calls[0]["image_inputs"][0]["role"] == "reference_image"
    assert character.full_body_image_url is not None
    assert character.headshot_image_url is not None
    assert character.turnaround_image_url is not None


@pytest.mark.asyncio
async def test_character_turnaround_video_retries_with_asset_library_after_privacy_failure(
    db_session,
    monkeypatch,
):
    project = Project(
        name="雨夜",
        story="story",
        ratio="9:16",
        stage="storyboard_ready",
        character_style_reference_image_url="projects/p/style/ref.png",
    )
    db_session.add(project)
    await db_session.flush()
    character = Character(project_id=project.id, name="秦昭", role_type="supporting", summary="少年天子")
    db_session.add(character)
    await db_session.flush()
    job = Job(
        project_id=project.id,
        kind="gen_character_asset_single",
        status="queued",
        target_type="character",
        target_id=character.id,
    )
    db_session.add(job)
    await db_session.commit()

    class FakeImageClient:
        async def image_generations(self, model, prompt, **kwargs):
            return {"data": [{"url": f"https://volcano.example/tmp-{prompt[:2]}.png"}]}

    video_calls: list[dict] = []

    class FakeVideoClient:
        async def video_generations_create(self, **kwargs):
            video_calls.append(kwargs)
            if len(video_calls) == 1:
                raise VolcanoContentFilterError("参考图被平台判定含隐私或敏感信息")
            return {"id": "video-task-asset-retry"}

        async def video_generations_get(self, task_id):
            return {
                "id": task_id,
                "status": "succeeded",
                "content": {"video_url": "https://volcano.example/turnaround.mp4"},
            }

    async def fake_persist_generated_asset(*, url, project_id, kind, ext="png"):
        return f"projects/{project_id}/{kind}/{url.rsplit('/', 1)[-1]}.{ext}"

    async def fake_register_asset_steps(session, character, on_step=None):
        character.video_style_ref = {
            "asset_group_id": "group-001",
            "asset_id": "asset-registered-char-001",
            "asset_status": "Active",
        }
        await session.flush()

    class FakeAssetClient:
        async def create_asset(self, group_id, url, asset_type="Image", name=""):
            assert group_id == "group-001"
            assert "/character_headshot/" in url
            return {"Id": "asset-registered-headshot-001"}

        async def wait_asset_active(self, asset_id, *, timeout=None, interval=None):
            assert asset_id == "asset-registered-headshot-001"
            return {"Status": "Active"}

        async def aclose(self):
            return None

    task_module = import_module("app.tasks.ai.gen_character_asset")
    character_service_module = import_module("app.domain.services.character_service")
    monkeypatch.setattr(task_module, "get_character_image_client", lambda: FakeImageClient())
    monkeypatch.setattr(task_module, "get_volcano_client", lambda: FakeVideoClient())
    monkeypatch.setattr(task_module, "get_volcano_asset_client", lambda: FakeAssetClient())
    monkeypatch.setattr(task_module, "persist_generated_asset", fake_persist_generated_asset)
    monkeypatch.setattr(
        character_service_module.CharacterService,
        "_register_asset_steps",
        staticmethod(fake_register_asset_steps),
    )

    await run_character_asset_generation(character.id, job.id, session=db_session)

    await db_session.refresh(character)
    await db_session.refresh(job)
    assert job.status == "succeeded"
    assert character.video_style_ref["asset_id"] == "asset-registered-char-001"
    assert character.turnaround_image_url and character.turnaround_image_url.endswith(".mp4")
    assert len(video_calls) == 2
    assert video_calls[1]["image_inputs"][0]["role"] == "first_frame"
    assert video_calls[1]["image_inputs"][0]["url"] == "asset://asset-registered-char-001"
    assert video_calls[1]["image_inputs"][1]["role"] == "last_frame"
    assert video_calls[1]["image_inputs"][1]["url"] == "asset://asset-registered-headshot-001"


@pytest.mark.asyncio
async def test_character_asset_regeneration_replaces_existing_full_body(db_session, monkeypatch):
    project = Project(
        name="雨夜",
        story="story",
        ratio="9:16",
        stage="storyboard_ready",
        character_style_reference_image_url="projects/p/style/ref.png",
    )
    db_session.add(project)
    await db_session.flush()
    character = Character(
        project_id=project.id,
        name="秦昭",
        role_type="supporting",
        summary="少年天子",
        full_body_image_url="projects/old/character_full_body/old.png",
        reference_image_url="projects/old/character_full_body/old.png",
        headshot_image_url="projects/old/character_headshot/old.png",
        turnaround_image_url="projects/old/character_turnaround/old.png",
    )
    db_session.add(character)
    await db_session.flush()
    job = Job(
        project_id=project.id,
        kind="gen_character_asset_single",
        status="queued",
        target_type="character",
        target_id=character.id,
    )
    db_session.add(job)
    await db_session.commit()
    calls: list[dict] = []

    class FakeImageClient:
        async def image_generations(self, model, prompt, **kwargs):
            calls.append({"model": model, "prompt": prompt, **kwargs})
            return {"data": [{"url": f"https://volcano.example/new-{len(calls)}.png"}]}

    class FakeVideoClient:
        async def video_generations_create(self, **kwargs):
            return {"id": "video-task-1"}

        async def video_generations_get(self, task_id):
            return {
                "id": task_id,
                "status": "succeeded",
                "content": {"video_url": "https://volcano.example/new-turnaround.mp4"},
            }

    async def fake_persist_generated_asset(*, url, project_id, kind, ext="png"):
        return f"projects/{project_id}/{kind}/{url.rsplit('/', 1)[-1]}"

    task_module = import_module("app.tasks.ai.gen_character_asset")
    monkeypatch.setattr(task_module, "get_character_image_client", lambda: FakeImageClient())
    monkeypatch.setattr(task_module, "get_volcano_client", lambda: FakeVideoClient())
    monkeypatch.setattr(task_module, "persist_generated_asset", fake_persist_generated_asset)

    await run_character_asset_generation(character.id, job.id, session=db_session, replace_existing=True)

    await db_session.refresh(character)
    assert character.full_body_image_url != "projects/old/character_full_body/old.png"
    assert character.reference_image_url == character.full_body_image_url
    assert character.headshot_image_url != "projects/old/character_headshot/old.png"
    assert character.turnaround_image_url != "projects/old/character_turnaround/old.png"
    assert "全身参考图" in calls[0]["prompt"]
    assert all(call["model"] == "gpt-image-2" for call in calls)
    assert "/character_full_body/" in calls[1]["references"][0]


@pytest.mark.asyncio
async def test_character_asset_generation_marks_parent_failed_when_child_fails(
    db_session,
    monkeypatch,
):
    project = Project(
        name="雨夜",
        story="story",
        ratio="9:16",
        stage="storyboard_ready",
    )
    db_session.add(project)
    await db_session.flush()
    character = Character(
        project_id=project.id,
        name="赵衡",
        role_type="supporting",
        summary="旧案真凶",
    )
    db_session.add(character)
    await db_session.flush()
    parent_job = Job(
        project_id=project.id,
        kind="gen_character_asset",
        status="running",
        progress=0,
        done=0,
        total=1,
    )
    db_session.add(parent_job)
    await db_session.flush()
    child_job = Job(
        project_id=project.id,
        parent_id=parent_job.id,
        kind="gen_character_asset_single",
        status="queued",
        target_type="character",
        target_id=character.id,
    )
    db_session.add(child_job)
    await db_session.commit()

    class FakeClient:
        async def image_generations(self, model, prompt, **kwargs):
            raise RuntimeError("InputTextSensitiveContentDetected")

    task_module = import_module("app.tasks.ai.gen_character_asset")
    monkeypatch.setattr(task_module, "get_character_image_client", lambda: FakeClient())

    await run_character_asset_generation(character.id, child_job.id, session=db_session)

    await db_session.refresh(parent_job)
    await db_session.refresh(child_job)
    assert child_job.status == "failed"
    assert parent_job.status == "failed"
    assert parent_job.done == 1
    assert parent_job.error_msg is not None
    assert "InputTextSensitiveContentDetected" in parent_job.error_msg
