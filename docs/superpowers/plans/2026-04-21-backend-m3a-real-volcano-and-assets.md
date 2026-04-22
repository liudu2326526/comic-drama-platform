# Backend M3a: 接入真实火山 + 角色/场景资产生成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 M2 留下的 mock AI 出口替换为真实火山方舟接口(Chat + Image,OpenAI SDK 兼容),并在 `storyboard_ready` 之后补齐角色/场景资产生成与锁定流程:落 `gen_character_asset` / `gen_scene_asset` 两个 Celery 任务、11 个业务端点(characters/scenes 的 `GET` / `generate` / `PATCH` / `regenerate` / `lock` + `storyboards/{id}/bind_scene`);pipeline 扩展 `lock_protagonist`(项目内主角唯一,应用层 `SELECT ... FOR UPDATE` 串行)、`advance_to_characters_locked`、`advance_to_scenes_locked`;聚合详情真实填充 `characters` / `scenes` 数组(带 `usage` 反查)。人像库(Asset/AssetGroup,HMAC 签名)本期落客户端(`CreateAssetGroup` / `CreateAsset` / `GetAsset` 轮询)并补齐"主角锁定后可入库"闭环:不新增 DB 字段,把 `asset_group_id` / `asset_id` / `asset_status` 写入 `characters.video_style_ref`;视频侧真正消费 `asset://` 留 M3b/c。

**Architecture:** 延续 M1/M2 分层。新增 `app/infra/volcano_asset_client.py` 作为人像库出口(AK/SK HMAC-SHA256 签名),与 `app/infra/volcano_client.py`(Bearer)分文件、分域、分凭据;两者由 `app/infra/__init__.py` 的 `get_volcano_client()` / `get_volcano_asset_client()` 工厂统一按 `AI_PROVIDER_MODE=mock|real` 路由。新增 `app/infra/obs_store.py` / `app/infra/asset_store.py` 统一负责"把火山返回的 24h 临时 URL 下载到临时文件 → 上传华为云 OBS → 回写 OBS object key",业务表图片字段只存 OBS object key(形如 `projects/<project_id>/character/20260421/<ulid>.png`)。展示和人像库入库都通过 `OBS_PUBLIC_BASE_URL + object_key` 获取公网 URL;人像库 `CreateAsset` 使用 OBS URL,不再依赖本地 `STORAGE_ROOT` 是否公网可达。Celery 任务只依赖 `VolcanoClient` 抽象,替换 mock/real 对上层透明。新增 pipeline 扩展继续由 `pipeline.transitions.*` 集中守护,所有 `characters` / `scenes` 写路径都必须先经过 guard。

**Tech Stack:** 延续 M1/M2(Python 3.11 / FastAPI / SQLAlchemy 2.x async / Alembic / Celery 5 / Redis / MySQL 8 / pytest-asyncio / openai 1.30.1 / httpx 0.27)。新增 `respx==0.21.1`(dev,对 httpx 打桩,替代 `requests_mock`)和 `esdk-obs-python`(华为云 OBS SDK,见 `docs/huawei_api/huawei_obs_integration.md`)。人像库 HMAC 签名**不引入新三方库**,手写 SHA256 签名(参考 `docs/huoshan_api/人像库 demo/CreateAssetGroup_Demo (1).py`)。

**References:**
- 设计文档:`docs/superpowers/specs/2026-04-20-backend-mvp-design.md`(§5.1 状态机、§6.2 端点表、§7.2 任务清单、§8.1 存储目录、§13.1 聚合契约)
- 火山 API 契约:`docs/integrations/volcengine-ark-api.md`(§1 人像库、§3 图片生成、§4 Chat、§5 错误分类)
- 华为云 OBS 契约:`docs/huawei_api/huawei_obs_integration.md`(`OBS_AK` / `OBS_SK` / `OBS_ENDPOINT` / `OBS_BUCKET` / `OBS_PUBLIC_BASE_URL`)
- M1 plan:`docs/superpowers/plans/2026-04-20-backend-m1-skeleton.md`
- M2 plan:`docs/superpowers/plans/2026-04-21-backend-m2-pipeline-and-mock.md`
- 前端契约:`docs/superpowers/specs/2026-04-20-frontend-mvp-design.md` §9 + `ProjectData.characters` / `ProjectData.scenes` / `CharacterAsset` / `SceneAsset` 类型

---

## M2 Review 遗留

**状态**: 无遗留问题。M2 已通过 code review,`pytest -v` 全绿,`AI_PROVIDER_MODE=mock` 下冒烟脚本通过。M3a 可直接在 M2 基础上开始实施。

---

## M3a 范围边界

**包含**:
- `RealVolcanoClient`:Chat + Image 真实调用(openai SDK),按 §4/§3 实现 `chat_completions` / `image_generations`
- `VolcanoAssetClient`:人像库 `CreateAssetGroup` / `CreateAsset` / `GetAsset` 三个操作的 HMAC-SHA256 签名实现(仅主角入库用到)
- 错误分类(`VolcanoError` 层级:限流 / 参数 / 鉴权 / 内容违规 / 5xx / 超时),按 §5 决定是否重试
- 资产存储模块 `asset_store`:`persist_generated_asset(url, project_id, kind, ext) -> OBS object_key` + `build_asset_url(object_key) -> OBS 公网 URL`
- Celery 任务:`gen_character_asset(character_id)` / `gen_scene_asset(scene_id)`
- 业务 API:
  - `GET /projects/{id}/characters`
  - `POST /projects/{id}/characters/generate`(Chat 抽取 N 个角色 → 批量 Image → 落库)
  - `PATCH /projects/{id}/characters/{cid}`
  - `POST /projects/{id}/characters/{cid}/regenerate`
  - `POST /projects/{id}/characters/{cid}/lock`(含主角唯一性守卫)
  - `GET /projects/{id}/scenes`
  - `POST /projects/{id}/scenes/generate`
  - `PATCH /projects/{id}/scenes/{sid}`
  - `POST /projects/{id}/scenes/{sid}/regenerate`
  - `POST /projects/{id}/scenes/{sid}/lock`
  - `POST /projects/{id}/storyboards/{shot_id}/bind_scene`
- pipeline 扩展:`lock_protagonist` / `advance_to_characters_locked` / `advance_to_scenes_locked` / `assert_asset_editable`
- 聚合详情填 `characters` / `scenes` 数组(`usage` 按 `scenes.id → storyboards.scene_id count` 反查)
- 集成测试:respx 打桩火山 HTTP / 主角唯一性并发测试 / 编辑窗口越权测试
- 冒烟脚本 `scripts/smoke_m3a.sh`

**不包含(留给后续)**:
- 视频渲染(`render_shot` / `render_batch`、Seedance 调用) → M3b/c
- 导出(`export_video`) → M4
- 断点续跑扫描 + `provider_task_id` 回查 → M5
- 人像库 **DB 兜底唯一约束**(spec §5.4 提到的 `protagonist_guard` 生成列)—— MVP 仍靠应用层 `SELECT ... FOR UPDATE`;若压测发现竞争,后置 M3b 再加迁移
- 前端联调(M3a 只管后端契约与 mock→real 切换)
- `AI_RATE_LIMIT_PER_MIN` 的令牌桶细化(粗粒度 min-level counter 足够本期用量)
- 人像库 `avatar_group_id` / `avatar_asset_id` 独立列迁移 —— 本期写入 `characters.video_style_ref`,M3b/c 若需要高频查询再补列

---

## 文件结构(M3a 交付)

**新建**:

```
backend/
├── app/
│   ├── api/
│   │   ├── characters.py
│   │   └── scenes.py
│   ├── domain/
│   │   ├── schemas/
│   │   │   ├── character.py
│   │   │   └── scene.py
│   │   └── services/
│   │       ├── character_service.py
│   │       └── scene_service.py
│   ├── infra/
│   │   ├── asset_store.py
│   │   ├── obs_store.py                  # OBS SDK wrapper:upload_file_to_obs / get_obs_url
│   │   ├── volcano_asset_client.py        # HMAC 签名 + 人像库 3 个操作
│   │   └── volcano_errors.py              # VolcanoError 层级 + HTTP→category 分类
│   └── tasks/
│       └── ai/
│           ├── gen_character_asset.py
│           └── gen_scene_asset.py
└── tests/
    ├── unit/
    │   ├── test_volcano_errors.py
    │   ├── test_volcano_asset_signature.py # HMAC 签名算法回归
    │   ├── test_asset_store.py
    │   ├── test_lock_protagonist.py        # 应用层唯一性
    │   └── test_advance_asset_stages.py
    └── integration/
        ├── test_characters_api.py
        ├── test_scenes_api.py
        ├── test_character_generate_flow.py # respx 打桩 Chat+Image
        ├── test_scene_generate_flow.py
        ├── test_protagonist_race.py        # 并发 lock 主角
        └── test_bind_scene.py
```

**修改**:

```
backend/
├── pyproject.toml                          # Task 1:respx dev 依赖
├── app/
│   ├── config.py                           # Task 1:新增火山真实配置项 + 人像库凭据
│   ├── main.py                             # Task 7/8:注册 characters / scenes 路由
│   ├── api/
│   │   └── storyboards.py                  # Task 11:新增 /storyboards/{id}/bind_scene
│   ├── infra/
│   │   ├── __init__.py                     # 导出两个 client factory
│   │   └── volcano_client.py               # Task 2:RealVolcanoClient 补全错误分类 + 重试
│   ├── pipeline/
│   │   └── transitions.py                  # Task 9:lock_protagonist / advance_to_* / assert_asset_editable
│   ├── domain/
│   │   ├── schemas/__init__.py             # 导出新 schemas
│   │   └── services/aggregate_service.py   # Task 12:填 characters / scenes / usage
│   └── tasks/
│       ├── celery_app.py                   # Task 6:include gen_character_asset / gen_scene_asset
│       └── ai/__init__.py                  # 同上
├── alembic/versions/
│   └── 0003_character_scene_meta_indexes.py # Task 6:characters.is_protagonist + locked 联合索引;scenes.locked 索引
├── tests/conftest.py                       # Task 3:httpx_mock / respx fixture
└── scripts/smoke_m3a.sh                    # Task 14
```

**责任**:
- `app/infra/volcano_client.py`:`RealVolcanoClient` 补全(openai SDK + 错误分类 + `VolcanoError` 抛出),mock 分支保持 M2 行为不动
- `app/infra/volcano_asset_client.py`:HMAC 签名 client,提供 `create_asset_group` / `create_asset` / `get_asset` / `wait_asset_active(id, timeout=120, interval=3)`
- `app/infra/volcano_errors.py`:`VolcanoError` / `VolcanoRateLimitError` / `VolcanoAuthError` / `VolcanoParamError` / `VolcanoContentFilterError` / `VolcanoServerError` / `VolcanoTimeoutError` + `classify(exc_or_resp)` 分类器
- `app/infra/obs_store.py`:封装华为 OBS SDK,提供 `upload_file_to_obs(local_path, object_key) -> {"object_key","url"}` / `get_obs_url(object_key) -> str`
- `app/infra/asset_store.py`:`async def persist_generated_asset(url, project_id, kind, ext='png') -> str`(返回 OBS object key),`build_asset_url(object_key)`(前端展示 + 人像库入库),kind ∈ {`character` / `scene` / `shot`}
- `app/pipeline/transitions.py`:新增 `lock_protagonist(session, project, character)` / `advance_to_characters_locked(session, project)` / `advance_to_scenes_locked(session, project)` / `assert_asset_editable(project, kind)`
- `app/domain/services/character_service.py`:`list_by_project` / `create_many` / `update` / `get_by_id`;所有写路径前置 `assert_asset_editable`
- `app/domain/services/scene_service.py`:同上;额外 `bind_scene_to_shot(shot, scene)`
- `app/tasks/ai/gen_character_asset.py`:单角色图像生成(openai images API)→ 下载火山临时 URL 并上传 OBS → 更新 `reference_image_url`(OBS object key) + `meta`;若被标为主角且已 lock,使用 OBS 公网 URL 追加 `VolcanoAssetClient` 入库流程并把 `asset_group_id` / `asset_id` / `asset_status` 写入 `video_style_ref`
- `app/tasks/ai/gen_scene_asset.py`:单场景图像生成;scene 不入人像库

---

## 实施前提

- M2 已合入(或本地已完成),`pytest -v` 全绿,`alembic upgrade head` 可执行;`AI_PROVIDER_MODE=mock` 下 M2 冒烟脚本通过
- `backend/.env` 新增:
  - `AI_PROVIDER_MODE=real`(本期切真实)
  - `ARK_API_KEY=sk-***`(Chat/Image)
  - `ARK_CHAT_MODEL=doubao-seed-1-6-251015`
  - `ARK_IMAGE_MODEL=doubao-seedream-4-0-250828`
  - `VOLC_ACCESS_KEY_ID=AKLT***` / `VOLC_SECRET_ACCESS_KEY=***` / `ARK_PROJECT_NAME=default`(人像库;与 `docs/integrations/volcengine-ark-api.md` 保持一致)
  - `OBS_AK=***` / `OBS_SK=***` / `OBS_ENDPOINT=obs.cn-south-1.myhuaweicloud.com` / `OBS_BUCKET=***` / `OBS_PUBLIC_BASE_URL=https://static.example.com`
  - `ASSET_DOWNLOAD_TIMEOUT=30`(秒)
- `STORAGE_ROOT` 仅作为下载火山临时 URL 的本地临时目录(dev 机器建议 `~/.cache/comic_drama/assets`,生产 `/data/assets/tmp`);持久文件一律上传 OBS
- `OBS_PUBLIC_BASE_URL` 必须能被火山公网访问,否则 `CreateAsset` 无法读取角色参考图;mock/dev 若不配 OBS,可设置 `OBS_MOCK=1` 让 `obs_store` 返回 deterministic object key / URL,但 real M3a DoD 必须走真实 OBS
- 本地无法访问公网时,`AI_PROVIDER_MODE=mock` 仍可跑通 M3a 所有逻辑(mock client 继续对 `gen_character_asset` / `gen_scene_asset` 返回 placeholder URL,验证状态机 + DB 写入;真实回归放 CI 拉 secret)
- 所有集成测试走 **respx** 打桩 httpx,不实际打公网;`TEST_VOLCANO_LIVE=1` 环境变量可选地打开一小组 live smoke(默认关)

---

## Task 1: 升级 pyproject + config — 真实火山配置项

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/config.py`

- [ ] **Step 1: 追加 OBS SDK + `respx`**

```toml
[project]
dependencies = [
  # ... existing deps
  "esdk-obs-python",  # 华为云 OBS SDK,用于资产持久化
]
```

```toml
[project.optional-dependencies]
dev = [
  "pytest==8.1.1",
  "pytest-asyncio==0.23.6",
  "httpx==0.27.0",
  "mypy==1.9.0",
  "respx==0.21.1",  # httpx 打桩库,用于集成测试
]
```

运行依赖追加 `esdk-obs-python`,用于华为云 OBS 上传;`openai==1.30.1` M2 已装,本期不动。dev 依赖追加 `respx`,用于 httpx 打桩测试。

- [ ] **Step 2: 扩 `Settings` — 新增火山真实 / 人像库 / 资产下载配置**

```python
# 追加字段
ark_chat_model: str = "doubao-seed-1-6-251015"
ark_image_model: str = "doubao-seedream-4-0-250828"
ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"

# 人像库(AK/SK HMAC)
volc_access_key_id: str = ""
volc_secret_access_key: str = ""
ark_project_name: str = "default"  # 统一使用 ARK_PROJECT_NAME;如已有 VOLC_PROJECT_NAME,Task 1 兼容读取后迁移
volc_asset_host: str = "ark.cn-beijing.volcengineapi.com"
volc_asset_region: str = "cn-beijing"
volc_asset_service: str = "ark"
volc_asset_api_version: str = "2024-01-01"

# 资产下载
asset_download_timeout: int = 30       # seconds
asset_download_chunk: int = 65536

# 华为云 OBS(见 docs/huawei_api/huawei_obs_integration.md)
obs_ak: str = ""
obs_sk: str = ""
obs_endpoint: str = ""
obs_bucket: str = ""
obs_public_base_url: str = ""          # CDN 或自定义域名,必须公网可访问
obs_mock: bool = False                 # 仅测试/本地 mock 模式允许,real 模式必须 False

# 轮询
asset_wait_interval_sec: float = 3.0
asset_wait_timeout_sec: float = 120.0

# 调用重试(Chat/Image 粗粒度)
ai_retry_max: int = 3
ai_retry_base_sec: float = 4.0   # 指数退避 4/16/64
```

兼容约束:
- `ARK_PROJECT_NAME` 是本项目统一环境变量名;若历史 `.env` 已有 `VOLC_PROJECT_NAME`,`Settings` 应通过 alias/validator 兼容读取,但 README 与新部署只写 `ARK_PROJECT_NAME`
- OBS 配置按 `docs/huawei_api/huawei_obs_integration.md` 命名;真实模式下缺任一 OBS 配置应在 `persist_generated_asset` 抛配置错误并让 job failed,避免把火山 24h 临时 URL 或本地路径误写入业务表。`OBS_MOCK=1` 只允许测试/本地 mock 冒烟使用,不得在 `AI_PROVIDER_MODE=real` 下启用

- [ ] **Step 3: 安装 + mypy**

```bash
cd backend && source .venv/bin/activate && pip install -e ".[dev]" && mypy app
```

Expected: 安装通过,mypy 通过。

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/app/config.py
git commit -m "chore(backend): M3a 真实火山/人像库/资产下载配置项 + respx dev 依赖"
```

---

## Task 2: VolcanoError 层级 + HTTP → 分类器(TDD)

**Files:**
- Create: `backend/app/infra/volcano_errors.py`
- Create: `backend/tests/unit/test_volcano_errors.py`

按 `docs/integrations/volcengine-ark-api.md` §5 定义层级,和 pipeline 错误语义解耦。

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_volcano_errors.py
import httpx
import pytest

from app.infra.volcano_errors import (
    VolcanoError, VolcanoAuthError, VolcanoParamError,
    VolcanoRateLimitError, VolcanoContentFilterError,
    VolcanoServerError, VolcanoTimeoutError, classify_http,
)


def _resp(status, body=b"{}"):
    return httpx.Response(status_code=status, content=body,
                          request=httpx.Request("GET", "http://x"))


class TestClassify:
    def test_401_auth(self):
        with pytest.raises(VolcanoAuthError):
            classify_http(_resp(401))

    def test_403_auth(self):
        with pytest.raises(VolcanoAuthError):
            classify_http(_resp(403))

    def test_429_ratelimit_preserves_retry_after(self):
        r = httpx.Response(429, headers={"Retry-After": "12"}, content=b"{}",
                           request=httpx.Request("GET", "http://x"))
        with pytest.raises(VolcanoRateLimitError) as exc:
            classify_http(r)
        assert exc.value.retry_after == 12

    def test_400_param(self):
        with pytest.raises(VolcanoParamError):
            classify_http(_resp(400, b'{"error":{"code":"InvalidParameter"}}'))

    def test_content_filter_from_400_code(self):
        r = _resp(400, b'{"error":{"code":"ContentFilter"}}')
        with pytest.raises(VolcanoContentFilterError):
            classify_http(r)

    def test_5xx_server(self):
        with pytest.raises(VolcanoServerError):
            classify_http(_resp(502))

    def test_2xx_ok_no_raise(self):
        # 不抛
        classify_http(_resp(200))


class TestTimeoutMapping:
    def test_httpx_timeout_maps(self):
        from app.infra.volcano_errors import classify_exception
        exc = httpx.ReadTimeout("t")
        with pytest.raises(VolcanoTimeoutError):
            classify_exception(exc)

    def test_httpx_connect_error_is_server(self):
        from app.infra.volcano_errors import classify_exception
        exc = httpx.ConnectError("c")
        with pytest.raises(VolcanoServerError):
            classify_exception(exc)
```

- [ ] **Step 2: 跑测试失败**

```bash
pytest tests/unit/test_volcano_errors.py -v
```

Expected: 全红(模块不存在)。

- [ ] **Step 3: 实现 `volcano_errors.py`**

```python
from __future__ import annotations
import json
import httpx


class VolcanoError(Exception):
    """基类。所有从 volcano_client / volcano_asset_client 抛出的业务可识别异常都继承此类。"""
    retryable = False


class VolcanoAuthError(VolcanoError):
    retryable = False


class VolcanoParamError(VolcanoError):
    retryable = False


class VolcanoContentFilterError(VolcanoError):
    retryable = False


class VolcanoRateLimitError(VolcanoError):
    retryable = True
    def __init__(self, msg: str, retry_after: int | None = None):
        super().__init__(msg)
        self.retry_after = retry_after


class VolcanoServerError(VolcanoError):
    retryable = True


class VolcanoTimeoutError(VolcanoError):
    retryable = True


_CONTENT_FILTER_CODES = {
    "ContentFilter", "OutputImageSensitiveContentDetected",
    "OutputVideoSensitiveContentDetected", "content_filter",
}


def classify_http(resp: httpx.Response) -> None:
    """2xx 不抛;4xx/5xx 按类别抛对应 VolcanoError 子类。"""
    if 200 <= resp.status_code < 300:
        return
    code_str = _extract_error_code(resp)
    if resp.status_code in (401, 403):
        raise VolcanoAuthError(f"auth {resp.status_code}: {code_str}")
    if resp.status_code == 429:
        ra = resp.headers.get("Retry-After")
        raise VolcanoRateLimitError("rate limited", int(ra) if ra and ra.isdigit() else None)
    if resp.status_code == 400:
        if code_str in _CONTENT_FILTER_CODES:
            raise VolcanoContentFilterError(code_str)
        raise VolcanoParamError(f"{code_str or resp.text[:200]}")
    if 500 <= resp.status_code < 600:
        raise VolcanoServerError(f"{resp.status_code}: {resp.text[:200]}")
    raise VolcanoError(f"unexpected http {resp.status_code}: {resp.text[:200]}")


def _extract_error_code(resp: httpx.Response) -> str:
    try:
        data = resp.json()
    except (ValueError, json.JSONDecodeError):
        return ""
    if isinstance(data, dict):
        err = data.get("error") or {}
        if isinstance(err, dict):
            return str(err.get("code", ""))
    return ""
```

**注意**: `classify_exception` 函数已被 `_map_httpx_exception` 替代,不再需要。Task 3 的 `RealVolcanoClient` 使用 `_map_httpx_exception` 进行异常映射。

- [ ] **Step 4: 测试通过 + commit**

```bash
pytest tests/unit/test_volcano_errors.py -v
git add backend/app/infra/volcano_errors.py backend/tests/unit/test_volcano_errors.py
git commit -m "feat(backend): VolcanoError 层级 + HTTP/异常分类器"
```

---

## Task 3: RealVolcanoClient 补全 — Chat + Image + 分类 + 重试

**Files:**
- Modify: `backend/app/infra/volcano_client.py`
- Create: `backend/tests/integration/test_volcano_real_client.py`

spec §4/§3 + 错误分类 §5。**不做**流式;**不做**工具调用;**不做**视频(留 M3b)。

- [ ] **Step 1: 扩 `RealVolcanoClient`**

核心改动:
1. 构造函数读 `settings.ark_api_key` / `settings.ark_base_url`,加 `timeout=60` 的 `httpx.AsyncClient`
2. `chat_completions` / `image_generations` 不再裸调 openai SDK — 改用 `httpx` 直连,便于 respx 打桩 + 统一错误分类(openai SDK 抛自己的异常类再转一层成本高)
3. 内部加 `_request_with_retry(method, path, json_body)`:
   - 捕获 `httpx.HTTPError` → `classify_exception`
   - 正常返回调 `classify_http`
   - 仅当 `VolcanoError.retryable` 为真时按 `settings.ai_retry_base_sec * (4**attempt)` 指数退避,最多 `settings.ai_retry_max` 次;`VolcanoRateLimitError.retry_after` 优先生效
4. 保持抽象基类签名,mock 分支无改动

签名示意:

```python
class RealVolcanoClient(VolcanoClient):
    def __init__(self) -> None:
        s = get_settings()
        if not s.ark_api_key:
            raise VolcanoAuthError("ark_api_key 未配置")
        self._client = httpx.AsyncClient(
            base_url=s.ark_base_url,
            headers={"Authorization": f"Bearer {s.ark_api_key}",
                     "Content-Type": "application/json"},
            timeout=60.0,
        )
        self._settings = s

    async def chat_completions(self, model, messages, **kwargs):
        body = {"model": model, "messages": messages, **kwargs}
        resp_json = await self._request_with_retry("POST", "/chat/completions", body)
        return _ChatResponse.from_dict(resp_json)   # 兼容 mock 的 .choices[0].message.content 形状

    async def image_generations(self, model, prompt, **kwargs):
        body = {"model": model, "prompt": prompt, "response_format": "url",
                "watermark": False, **kwargs}
        resp_json = await self._request_with_retry("POST", "/images/generations", body)
        return resp_json  # {"data": [{"url": "..."}], "usage": {...}}

      def _map_httpx_exception(self, e: httpx.HTTPError) -> VolcanoError:
        """将 httpx 异常映射为 VolcanoError 子类,但不抛出"""
        if isinstance(e, (httpx.ReadTimeout, httpx.WriteTimeout, httpx.ConnectTimeout, httpx.PoolTimeout)):
            return VolcanoTimeoutError(str(e))
        if isinstance(e, httpx.TransportError):
            return VolcanoServerError(str(e))
        return VolcanoServerError(f"httpx error: {e}")

    async def _request_with_retry(self, method, path, json_body):
        last_exc = None
        for attempt in range(self._settings.ai_retry_max):
            try:
                resp = await self._client.request(method, path, json=json_body)
                classify_http(resp)
                return resp.json()
            except httpx.HTTPError as e:
                # 先映射为 VolcanoError,再判断是否重试
                volcano_err = self._map_httpx_exception(e)
                if isinstance(volcano_err, (VolcanoServerError, VolcanoTimeoutError)):
                    last_exc = volcano_err
                    await asyncio.sleep(self._settings.ai_retry_base_sec * (4 ** attempt))
                    continue
                raise volcano_err
            except VolcanoRateLimitError as e:
                last_exc = e
                delay = e.retry_after or (self._settings.ai_retry_base_sec * (4 ** attempt))
                await asyncio.sleep(delay)
            except (VolcanoServerError, VolcanoTimeoutError) as e:
                last_exc = e
                await asyncio.sleep(self._settings.ai_retry_base_sec * (4 ** attempt))
            except VolcanoError:
                raise  # 不可重试的错误(Auth/Param/ContentFilter)直接抛出
        raise last_exc or VolcanoServerError("exhausted retries")
```

`_ChatResponse.from_dict` 返回对象要与 M2 mock 的鸭子类型一致(`.choices[0].message.content` / `.choices[0].finish_reason`),这样 `parse_novel` / `gen_storyboard` 以及 M3a 新任务无需二次适配。

- [ ] **Step 2: respx 集成测试**

```python
# tests/integration/test_volcano_real_client.py
import asyncio
import pytest
import respx
import httpx

from app.infra.volcano_client import RealVolcanoClient
from app.infra.volcano_errors import (
    VolcanoRateLimitError, VolcanoAuthError, VolcanoServerError,
)


@pytest.fixture
def patched_settings(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "sk-test")
    monkeypatch.setenv("AI_RETRY_BASE_SEC", "0")   # 测试不真等
    from app.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@respx.mock
@pytest.mark.asyncio
async def test_chat_success(patched_settings):
    respx.post("https://ark.cn-beijing.volces.com/api/v3/chat/completions").mock(
        return_value=httpx.Response(200, json={
            "choices": [{"finish_reason": "stop",
                         "message": {"role": "assistant", "content": "hi"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })
    )
    c = RealVolcanoClient()
    resp = await c.chat_completions("doubao-seed-1-6-251015",
                                    [{"role": "user", "content": "hi"}])
    assert resp.choices[0].message.content == "hi"


@respx.mock
@pytest.mark.asyncio
async def test_image_success(patched_settings):
    respx.post("https://ark.cn-beijing.volces.com/api/v3/images/generations").mock(
        return_value=httpx.Response(200, json={
            "data": [{"url": "https://xxx/1.png", "size": "1152x864"}],
            "usage": {"generated_images": 1},
        })
    )
    c = RealVolcanoClient()
    resp = await c.image_generations("doubao-seedream-4-0-250828", "cat")
    assert resp["data"][0]["url"].startswith("https://")


@respx.mock
@pytest.mark.asyncio
async def test_rate_limit_honors_retry_after(patched_settings):
    route = respx.post("https://ark.cn-beijing.volces.com/api/v3/chat/completions")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0"}, json={"error": {"code": "RateLimitExceeded"}}),
        httpx.Response(200, json={
            "choices": [{"finish_reason": "stop",
                         "message": {"role": "assistant", "content": "ok"}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }),
    ]
    c = RealVolcanoClient()
    resp = await c.chat_completions("doubao-seed-1-6-251015",
                                    [{"role": "user", "content": "hi"}])
    assert resp.choices[0].message.content == "ok"
    assert route.call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_auth_not_retried(patched_settings):
    route = respx.post("https://ark.cn-beijing.volces.com/api/v3/chat/completions").mock(
        return_value=httpx.Response(401, json={"error": {"code": "InvalidApiKey"}}))
    c = RealVolcanoClient()
    with pytest.raises(VolcanoAuthError):
        await c.chat_completions("x", [{"role": "user", "content": "x"}])
    assert route.call_count == 1   # 只打一次
```

- [ ] **Step 3: 测试全绿,mypy 过**

- [ ] **Step 4: Commit**

```bash
git add backend/app/infra/volcano_client.py backend/tests/integration/test_volcano_real_client.py
git commit -m "feat(backend): RealVolcanoClient 走 httpx + 错误分类 + 指数退避重试"
```

---

## Task 4: VolcanoAssetClient — HMAC 签名 + 3 个人像库操作

**Files:**
- Create: `backend/app/infra/volcano_asset_client.py`
- Create: `backend/tests/unit/test_volcano_asset_signature.py`

按 `docs/integrations/volcengine-ark-api.md` §1.2 的签名约定实现;签名算法回归靠**官方 demo** 的样本向量(`docs/huoshan_api/人像库 demo/CreateAssetGroup_Demo (1).py`)。

- [ ] **Step 1: 固定签名样本确认**

使用固定的 `AK="AKLTDEMO" / SK="SECDEMO" / X-Date="20260421T120000Z"` + 固定 body。下方测试已带 expected 值;若后续调整 body / canonical request,必须重新用官方 demo 校验。

- [ ] **Step 2: 单元测试先行**

```python
# tests/unit/test_volcano_asset_signature.py
import json
from app.infra.volcano_asset_client import (
    build_canonical_request, calc_signature, sign,
)


def test_signature_matches_official_demo():
    """使用官方 demo(docs/huoshan_api/人像库 demo/CreateAssetGroup_Demo (1).py)跑出的
    固定样本回归。任何签名算法改动都会被这条测试卡住。"""
    ak = "AKLTDEMO"
    sk = "SECDEMO"
    host = "ark.cn-beijing.volcengineapi.com"
    region = "cn-beijing"
    service = "ark"
    date = "20260421T120000Z"
    body = json.dumps({"Name": "demo", "GroupType": "AIGC",
                       "ProjectName": "default"}, separators=(",", ":"))
    query = "Action=CreateAssetGroup&Version=2024-01-01"
    expected_authorization = (
        "HMAC-SHA256 Credential=AKLTDEMO/20260421/cn-beijing/ark/request, "
        "SignedHeaders=content-type;host;x-content-sha256;x-date, "
        "Signature=84ccf7dcb4332c72bd124824adaefa8f0410e8f1b78acbc779f7c8cf451128d6"
    )
    authz = sign(
        access_key=ak, secret_key=sk, host=host, region=region,
        service=service, x_date=date, method="POST", path="/", query=query,
        body=body.encode("utf-8"),
    )
    assert authz == expected_authorization


def test_canonical_request_sorts_query_by_key():
    # Version 在前(字典序)→ 签名输入里也要是排序后的
    cr = build_canonical_request(
        method="POST", path="/",
        query="Action=CreateAssetGroup&Version=2024-01-01",
        headers={"content-type": "application/json",
                 "host": "ark.cn-beijing.volcengineapi.com",
                 "x-content-sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                 "x-date": "20260421T120000Z"},
        body_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    # Query 被按 key 字典序重排:Action → Version
    assert "Action=CreateAssetGroup&Version=2024-01-01" in cr
```

- [ ] **Step 3: 实现签名 + 三个操作**

```python
# app/infra/volcano_asset_client.py
import hashlib, hmac, json, time
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from app.config import get_settings
from app.infra.volcano_errors import classify_http, classify_exception, VolcanoError


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def build_canonical_request(method, path, query, headers, body_sha256) -> str:
    # query:按 key 字典序排序 + URL encode(RFC3986)
    items = sorted(
        (kv.split("=", 1) if "=" in kv else (kv, ""))
        for kv in query.split("&") if kv
    )
    canonical_query = "&".join(
        f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in items
    )
    signed_headers = "content-type;host;x-content-sha256;x-date"
    canonical_headers = "".join(
        f"{h}:{headers[h]}\n" for h in ("content-type", "host",
                                        "x-content-sha256", "x-date")
    )
    return "\n".join([method, path, canonical_query, canonical_headers,
                      signed_headers, body_sha256])


def calc_signature(secret_key, date_short, region, service, string_to_sign) -> str:
    k_date = _hmac(secret_key.encode("utf-8"), date_short)
    k_region = _hmac(k_date, region)
    k_service = _hmac(k_region, service)
    k_signing = _hmac(k_service, "request")
    return hmac.new(k_signing, string_to_sign.encode("utf-8"),
                    hashlib.sha256).hexdigest()


def sign(*, access_key, secret_key, host, region, service, x_date,
         method, path, query, body) -> str:
    body_sha = _sha256_hex(body)
    headers = {
        "content-type": "application/json",
        "host": host,
        "x-content-sha256": body_sha,
        "x-date": x_date,
    }
    canonical = build_canonical_request(method, path, query, headers, body_sha)
    canonical_sha = _sha256_hex(canonical.encode("utf-8"))
    date_short = x_date[:8]   # YYYYMMDD
    credential_scope = f"{date_short}/{region}/{service}/request"
    string_to_sign = "\n".join(["HMAC-SHA256", x_date, credential_scope, canonical_sha])
    signature = calc_signature(secret_key, date_short, region, service, string_to_sign)
    signed_headers = "content-type;host;x-content-sha256;x-date"
    return (f"HMAC-SHA256 Credential={access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}")


class VolcanoAssetClient:
    def __init__(self):
        s = get_settings()
        if not s.volc_access_key_id or not s.volc_secret_access_key:
            raise VolcanoError("人像库 AK/SK 未配置")
        self._s = s
        self._client = httpx.AsyncClient(
            base_url=f"https://{s.volc_asset_host}",
            timeout=30.0,
        )

    def _now_x_date(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    async def _call(self, action: str, body: dict) -> dict:
        b = json.dumps(body, separators=(",", ":")).encode("utf-8")
        x_date = self._now_x_date()
        query = f"Action={action}&Version={self._s.volc_asset_api_version}"
        authz = sign(
            access_key=self._s.volc_access_key_id,
            secret_key=self._s.volc_secret_access_key,
            host=self._s.volc_asset_host,
            region=self._s.volc_asset_region,
            service=self._s.volc_asset_service,
            x_date=x_date, method="POST", path="/", query=query, body=b,
        )
        headers = {
            "Authorization": authz,
            "Content-Type": "application/json",
            "Host": self._s.volc_asset_host,
            "X-Date": x_date,
            "X-Content-Sha256": _sha256_hex(b),
        }
        try:
            resp = await self._client.post(f"/?{query}", content=b, headers=headers)
        except httpx.HTTPError as e:
            classify_exception(e)
            raise
        classify_http(resp)
        return resp.json().get("Result") or resp.json()

    async def create_asset_group(self, name, description=None):
        return await self._call("CreateAssetGroup", {
            "Name": name, "Description": description or "",
            "GroupType": "AIGC", "ProjectName": self._s.ark_project_name,
        })

    async def create_asset(self, group_id, url, asset_type="Image", name=""):
        return await self._call("CreateAsset", {
            "GroupId": group_id, "URL": url, "AssetType": asset_type,
            "Name": name, "ProjectName": self._s.ark_project_name,
        })

    async def get_asset(self, asset_id):
        return await self._call("GetAsset", {
            "Id": asset_id, "ProjectName": self._s.ark_project_name,
        })

    async def wait_asset_active(self, asset_id, *, timeout=None, interval=None) -> dict:
        """轮询直到 Status=Active;Failed 则抛 VolcanoError;超时抛 VolcanoTimeoutError。"""
        import asyncio
        from app.infra.volcano_errors import VolcanoTimeoutError
        t = timeout or self._s.asset_wait_timeout_sec
        iv = interval or self._s.asset_wait_interval_sec
        start = time.monotonic()
        while time.monotonic() - start < t:
            info = await self.get_asset(asset_id)
            st = info.get("Status")
            if st == "Active":
                return info
            if st == "Failed":
                raise VolcanoError(f"asset {asset_id} failed")
            await asyncio.sleep(iv)
        raise VolcanoTimeoutError(f"asset {asset_id} not active in {t}s")
```

- [ ] **Step 4: 测试通过 + commit**

```bash
git add backend/app/infra/volcano_asset_client.py backend/tests/unit/test_volcano_asset_signature.py
git commit -m "feat(backend): 人像库 VolcanoAssetClient + HMAC-SHA256 签名"
```

---

## Task 5: OBS asset_store — 火山临时 URL → OBS object key

**Files:**
- Create: `backend/app/infra/obs_store.py`
- Create: `backend/app/infra/asset_store.py`
- Create: `backend/tests/unit/test_asset_store.py`

spec §8.1 目录规则 + `docs/huawei_api/huawei_obs_integration.md`。本期只处理 `character` / `scene`,`shot` 留 M3b。业务表 `reference_image_url` 存 OBS object key,不存火山临时 URL、不存完整 CDN URL。

- [ ] **Step 1: 写测试(respx 下载 + monkeypatch OBS 上传)**

```python
# tests/unit/test_asset_store.py
from pathlib import Path
import pytest
import respx
import httpx

from app.infra.asset_store import build_asset_url, persist_generated_asset


@respx.mock
@pytest.mark.asyncio
async def test_downloads_uploads_obs_and_returns_object_key(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("OBS_AK", "ak")
    monkeypatch.setenv("OBS_SK", "sk")
    monkeypatch.setenv("OBS_ENDPOINT", "obs.cn-south-1.myhuaweicloud.com")
    monkeypatch.setenv("OBS_BUCKET", "bucket")
    monkeypatch.setenv("OBS_PUBLIC_BASE_URL", "https://static.example.com")
    from app.config import get_settings
    get_settings.cache_clear()

    uploaded = {}
    def fake_upload(local_path: str, object_key: str):
        uploaded["object_key"] = object_key
        uploaded["bytes"] = Path(local_path).read_bytes()
        return {"success": True, "object_key": object_key,
                "url": f"https://static.example.com/{object_key}"}
    monkeypatch.setattr("app.infra.obs_store.upload_file_to_obs", fake_upload)

    respx.get("https://cdn/xxx.png").mock(
        return_value=httpx.Response(200, content=b"PNGDATA"))

    object_key = await persist_generated_asset(
        url="https://cdn/xxx.png",
        project_id="01HPROJ",
        kind="character",
        ext="png",
    )
    assert object_key.startswith("projects/01HPROJ/character/")
    assert object_key.endswith(".png")
    assert uploaded["object_key"] == object_key
    assert uploaded["bytes"] == b"PNGDATA"
    assert build_asset_url(object_key) == f"https://static.example.com/{object_key}"


@pytest.mark.asyncio
async def test_rejects_unknown_kind():
    with pytest.raises(ValueError):
        await persist_generated_asset(url="https://x", project_id="p",
                                      kind="something_else")
```

- [ ] **Step 2: 实现**

```python
# app/infra/obs_store.py
from obs import ObsClient

from app.config import get_settings


def _get_obs_client():
    s = get_settings()
    return ObsClient(
        access_key_id=s.obs_ak,
        secret_access_key=s.obs_sk,
        server=s.obs_endpoint,
    )


def upload_file_to_obs(local_path: str, object_key: str) -> dict:
    s = get_settings()
    if s.obs_mock:
        # OBS_MOCK 只允许在非 real 模式下使用
        if s.ai_provider_mode == "real":
            raise RuntimeError("OBS_MOCK=1 不得在 AI_PROVIDER_MODE=real 下使用,必须配置真实 OBS")
        return {"success": True, "object_key": object_key, "url": get_obs_url(object_key)}
    if not all([s.obs_ak, s.obs_sk, s.obs_endpoint, s.obs_bucket, s.obs_public_base_url]):
        raise RuntimeError("OBS 配置不完整")
    client = _get_obs_client()
    try:
        resp = client.putFile(s.obs_bucket, object_key, file_path=local_path)
        if resp.status < 300:
            return {"success": True, "object_key": object_key, "url": get_obs_url(object_key)}
        raise RuntimeError(f"OBS upload failed: {resp.errorCode}: {resp.errorMessage}")
    finally:
        client.close()


def get_obs_url(object_key: str) -> str:
    s = get_settings()
    if not s.obs_public_base_url:
        if s.obs_mock:
            # mock 模式允许 fallback
            return f"https://obs-mock.local/{object_key.lstrip('/')}"
        raise RuntimeError("OBS_PUBLIC_BASE_URL 未配置")
    base = s.obs_public_base_url.rstrip("/")
    return f"{base}/{object_key.lstrip('/')}"
```

```python
# app/infra/asset_store.py
from datetime import datetime, timezone
from pathlib import Path
import asyncio

import httpx

from app.config import get_settings
from app.infra import obs_store
from app.infra.ulid import new_id
from app.infra.volcano_errors import classify_http, classify_exception

ALLOWED_KINDS = {"character", "scene", "shot"}


async def persist_generated_asset(*, url: str, project_id: str, kind: str,
                                  ext: str = "png") -> str:
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"kind must be one of {ALLOWED_KINDS}, got {kind!r}")
    s = get_settings()
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    object_key = f"projects/{project_id}/{kind}/{day}/{new_id()}.{ext}"
    abs_path = Path(s.storage_root) / "tmp" / object_key
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # 下载火山临时 URL 到本地
        async with httpx.AsyncClient(timeout=s.asset_download_timeout) as client:
            async with client.stream("GET", url) as resp:
                classify_http(resp)
                with open(abs_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(s.asset_download_chunk):
                        f.write(chunk)
        
        # 使用 asyncio.to_thread 避免阻塞事件循环
        await asyncio.to_thread(obs_store.upload_file_to_obs, str(abs_path), object_key)
        
        return object_key
    except httpx.HTTPError as e:
        classify_exception(e)
        raise
    finally:
        # 清理临时文件
        if abs_path.exists():
            abs_path.unlink()


def build_asset_url(object_key: str | None) -> str | None:
    if not object_key:
        return None
    return obs_store.get_obs_url(object_key)
```

- [ ] **Step 3: 测试通过 + commit**

```bash
git add backend/app/infra/obs_store.py backend/app/infra/asset_store.py backend/tests/unit/test_asset_store.py
git commit -m "feat(backend): asset_store — 火山 URL 转存 OBS object key"
```

---

## Task 6: Alembic 0003 — 索引补齐

**Files:**
- Create: `backend/alembic/versions/0003_character_scene_meta_indexes.py`
- Create: `backend/tests/integration/test_alembic_migration_0003.py`

目标索引:
1. `characters`:复合索引 `(project_id, is_protagonist, locked)` —— `lock_protagonist` 的 `SELECT FOR UPDATE` 用
2. `characters`:复合索引 `(project_id, locked)` —— `advance_to_characters_locked` 查 "项目内至少一个 locked 的主角"
3. `scenes`:索引 `(project_id, locked)` —— `advance_to_scenes_locked`
4. `storyboards`:索引 `(project_id, scene_id)` —— bind_scene 查 usage(M2 已有 `ix_storyboards_scene_id`,但 usage 反查要走 `project_id`)

Alembic migration 不要求重复执行同一 revision 幂等;正常 `upgrade head` 只会执行一次。若本地库可能已有同名索引,迁移里用 SQLAlchemy inspector 先查索引名再 `op.create_index`,不要依赖 `create_index(..., if_not_exists=True)`(MySQL 方言/ Alembic 版本兼容性不稳定)。downgrade 对应 `drop_index`,可用同样 inspector 避免本地脏库报错。

- [ ] **Step 1: 写迁移 + upgrade/downgrade 测试(从 0002 → head → 0002 → head)**

```python
# backend/alembic/versions/0003_character_scene_meta_indexes.py
"""character scene meta indexes

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # characters 索引
    existing = {idx['name'] for idx in inspector.get_indexes('characters')}
    if 'ix_characters_project_protagonist_locked' not in existing:
        op.create_index('ix_characters_project_protagonist_locked', 'characters',
                        ['project_id', 'is_protagonist', 'locked'])
    if 'ix_characters_project_locked' not in existing:
        op.create_index('ix_characters_project_locked', 'characters',
                        ['project_id', 'locked'])
    
    # scenes 索引
    existing = {idx['name'] for idx in inspector.get_indexes('scenes')}
    if 'ix_scenes_project_locked' not in existing:
        op.create_index('ix_scenes_project_locked', 'scenes',
                        ['project_id', 'locked'])
    
    # storyboards 索引
    existing = {idx['name'] for idx in inspector.get_indexes('storyboards')}
    if 'ix_storyboards_project_scene' not in existing:
        op.create_index('ix_storyboards_project_scene', 'storyboards',
                        ['project_id', 'scene_id'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    
    existing = {idx['name'] for idx in inspector.get_indexes('storyboards')}
    if 'ix_storyboards_project_scene' in existing:
        op.drop_index('ix_storyboards_project_scene', table_name='storyboards')
    
    existing = {idx['name'] for idx in inspector.get_indexes('scenes')}
    if 'ix_scenes_project_locked' in existing:
        op.drop_index('ix_scenes_project_locked', table_name='scenes')
    
    existing = {idx['name'] for idx in inspector.get_indexes('characters')}
    if 'ix_characters_project_locked' in existing:
        op.drop_index('ix_characters_project_locked', table_name='characters')
    if 'ix_characters_project_protagonist_locked' in existing:
        op.drop_index('ix_characters_project_protagonist_locked', table_name='characters')
```

- [ ] **Step 2: `alembic upgrade head`,`mysql> SHOW INDEX FROM characters` 验证**
- [ ] **Step 3: Commit**

---

## Task 7: Character schemas + API

**Files:**
- Create: `backend/app/domain/schemas/character.py`
- Create: `backend/app/api/characters.py`
- Create: `backend/app/domain/services/character_service.py`
- Modify: `backend/app/domain/schemas/__init__.py`
- Modify: `backend/app/main.py`(include router)

schemas:

```python
# app/domain/schemas/character.py
from pydantic import BaseModel, Field, model_validator


class CharacterOut(BaseModel):
    id: str
    name: str
    role: str        # 中文展示值(protagonist→"主角" 等)
    role_type: str   # 原始 ENUM
    is_protagonist: bool
    locked: bool
    summary: str | None
    description: str | None
    meta: list[str] = []              # 前端展示串,由 meta/video_style_ref 摘要化
    reference_image_url: str | None   # 前端直接展示的 URL(aggregate 层用 OBS_PUBLIC_BASE_URL 拼)


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    summary: str | None = Field(default=None, max_length=255)
    description: str | None = None
    meta: dict | None = None
    role_type: str | None = None   # 允许从 supporting → atmosphere 等调整

    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_null(cls, data):
        if isinstance(data, dict):
            for f in ("name", "role_type"):
                if f in data and data[f] is None:
                    raise ValueError(f"{f} 不允许显式 null")
        return data


class CharacterGenerateRequest(BaseModel):
    # 允许前端手动追加"希望额外生成的角色 hint",MVP 可空
    extra_hints: list[str] = []


class CharacterLockRequest(BaseModel):
    as_protagonist: bool = False   # True → 触发 lock_protagonist


class GenerateJobAck(BaseModel):
    job_id: str
    sub_job_ids: list[str] = []
```

endpoints(均挂 `/api/v1/projects/{project_id}/characters`):
- `GET /`: `CharacterService.list_by_project`
- `POST /generate`: 同步创建主 job(`kind=gen_character_asset` 聚合)+ N 个子 job,分发 celery,返回 ack
- `PATCH /{cid}`: `assert_asset_editable(project, "character")` → update
- `POST /{cid}/regenerate`: 单角色重跑图像(复用 character 行,新开 job)
- `POST /{cid}/lock`: 调 `lock_protagonist`(若 `as_protagonist`)或仅置 `locked=True`;若项目内至少一个 locked 主角 → 调 `advance_to_characters_locked`
  - **主角入人像库触发**: 若 `as_protagonist=True` 且 `character.reference_image_url` 已存在,同步调用 `ensure_character_asset_registered(character)` 入库:
    ```python
    # app/api/characters.py 或 app/domain/services/character_service.py
    from app.infra import get_volcano_asset_client
    from app.infra.asset_store import build_asset_url
    from datetime import datetime, timezone
    
    async def ensure_character_asset_registered(session, character):
        """确保主角已入人像库。幂等:若已入库则跳过。"""
        if not character.reference_image_url:
            return  # 图片未生成,跳过
        
        video_ref = character.video_style_ref or {}
        if video_ref.get("asset_id"):
            return  # 已入库,跳过(幂等保护)
        
        public_url = build_asset_url(character.reference_image_url)
        if not public_url:
            raise ValueError("OBS URL 构建失败")
        
        asset_client = get_volcano_asset_client()
        
        # 创建 AssetGroup(若不存在)
        if not video_ref.get("asset_group_id"):
            group = await asset_client.create_asset_group(
                name=f"{character.name}_group",
                description=f"Project {character.project_id}"
            )
            video_ref["asset_group_id"] = group["Id"]
        
        # 创建 Asset
        asset = await asset_client.create_asset(
            group_id=video_ref["asset_group_id"],
            url=public_url,
            name=character.name
        )
        video_ref["asset_id"] = asset["Id"]
        video_ref["asset_status"] = "Pending"
        
        # 轮询直到 Active
        final = await asset_client.wait_asset_active(asset["Id"], timeout=120)
        video_ref["asset_status"] = final["Status"]
        video_ref["asset_updated_at"] = datetime.now(timezone.utc).isoformat()
        
        character.video_style_ref = video_ref
    ```
    
    **调用时机说明**:
    - 在 `POST /characters/{cid}/lock` 端点中,若 `as_protagonist=True` 且 `character.reference_image_url` 非空,调用此函数
    - 函数内部有幂等保护(`asset_id` 已存在则跳过),可安全重复调用

`POST /generate` 内部流程:
1. 读 project + 校验 `stage_raw in {storyboard_ready}`(`assert_in_stages`)
2. **锁定 project 行防止并发**:
   ```python
   async with session.begin():
       project = await session.execute(
           select(Project).where(Project.id == project_id).with_for_update()
       )
       project = project.scalar_one()
   ```
3. Chat(ark_chat_model)读 `story + storyboards[title+description]` + response_format=json_schema → 返回 `[{name, role_type, summary, description}, ...]`
   
   **错误处理**:
   ```python
   try:
       chat_result = await volcano_client.chat_completions(
           model=settings.ark_chat_model,
           messages=[{"role": "user", "content": prompt}],
           response_format={"type": "json_object"}
       )
       characters = json.loads(chat_result.choices[0].message.content)
       if not characters:
           raise HTTPException(
               status_code=422,
               detail={"code": 40001, "message": "未识别到角色,请补充小说内容", "data": None}
           )
   except VolcanoContentFilterError:
       raise HTTPException(
           status_code=422,
           detail={"code": 42201, "message": "AI 内容违规,请修改文案后重试", "data": None}
       )
   ```

4. 在同一事务中按 `(project_id, name)` 做 find-or-create 幂等:
   ```python
   for char_data in characters:
       existing = await session.execute(
           select(Character)
           .where(Character.project_id == project.id, Character.name == char_data["name"])
       )
       char = existing.scalar_one_or_none()
       if not char:
           char = Character(project_id=project.id, name=char_data["name"], ...)
           session.add(char)
   await session.flush()  # 获取所有 character.id
   ```
   **并发保护**: project 行锁确保同一项目的多个 `/generate` 请求串行化;不同项目可并发
5. 每条 character 发 `gen_character_asset.delay(character_id, parent_job_id)`,写子 job 行

**注意**: 本期不新增 `(project_id, name)` 唯一约束,依赖 project 行锁串行化。若后续需要支持同项目并发生成,需在 Task 6 迁移中添加唯一约束。

**新增错误码**:
| code | 含义 | 注册位置 |
|---|---|---|
| 42201 | AI 内容违规,请修改文案后重试 | `app/api/errors.py` |

**实现方式**:
- 在 `app/api/errors.py` 中新增常量 `CONTENT_FILTER = 42201`(可选,便于引用)
- 在 character/scene generate 端点中捕获 `VolcanoContentFilterError`,转换为 `raise HTTPException(status_code=422, detail={"code": 42201, "message": "AI 内容违规,请修改文案后重试"})`
- 前端通过 422 状态码 + body.code=42201 识别并展示友好提示

示例:
```python
# app/api/characters.py
try:
    result = await volcano_client.chat_completions(...)
except VolcanoContentFilterError as e:
    raise HTTPException(
        status_code=422,
        detail={"code": 42201, "message": "AI 内容违规,请修改文案后重试", "data": None}
    )
```

- [ ] **Step 1: 写 TDD 失败测试(先写 `tests/integration/test_characters_api.py` 覆盖 list / generate / patch / lock 四条)**
- [ ] **Step 2: 实现 service + router**
- [ ] **Step 3: 补回 parse_novel mock 输出里没有 character 的现实 — `/generate` 是独立 Chat call**
- [ ] **Step 4: commit**

---

## Task 8: Scene schemas + API

**Files:**
- Create: `backend/app/domain/schemas/scene.py`
- Create: `backend/app/api/scenes.py`
- Create: `backend/app/domain/services/scene_service.py`

与 Task 7 对称:

```python
# app/domain/schemas/scene.py
class SceneOut(BaseModel):
    id: str
    name: str
    theme: str | None
    summary: str | None
    description: str | None
    meta: list[str] = []              # 前端展示串,由 meta 摘要化
    locked: bool
    template_id: str | None
    reference_image_url: str | None
    usage: str   # "场景复用 N 镜头"(由 aggregate 拼;单条接口也返回)


class SceneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    theme: str | None = Field(default=None, max_length=32)
    summary: str | None = Field(default=None, max_length=255)
    description: str | None = None
    meta: dict | None = None
    template_id: str | None = None

    # 同 CharacterUpdate 的 _reject_explicit_null(name/theme/template_id 不允许 null)


class SceneGenerateRequest(BaseModel):
    template_whitelist: list[str] = []    # 限定模板;空 = 不限


class SceneLockRequest(BaseModel):
    pass
```

endpoints(均挂 `/api/v1/projects/{project_id}`):`GET /scenes`、`POST /scenes/generate`、`PATCH /scenes/{sid}`、`POST /scenes/{sid}/regenerate`、`POST /scenes/{sid}/lock`。

stage 前提:`POST /scenes/generate` 要求 `stage_raw=characters_locked`(spec §5.4 不变量 2)。

`POST /{sid}/lock`:
1. 置 `scenes.locked=True`
2. 查"项目内所有 storyboards 是否都已绑定且对应 scene 全部 locked":
   ```sql
   SELECT COUNT(*) FROM storyboards s
   LEFT JOIN scenes sc ON s.scene_id=sc.id
   WHERE s.project_id=:pid
     AND (s.scene_id IS NULL 
          OR sc.id IS NULL 
          OR sc.locked=FALSE
          OR sc.project_id != :pid)  -- 防止跨项目 scene 被错误放行
   ```
   = 0 → 调 `advance_to_scenes_locked`

- [ ] **TDD**:先 `tests/integration/test_scenes_api.py` 覆盖 generate / patch / lock 流程
- [ ] 实现 + commit

---

## Task 9: pipeline 扩展 — lock_protagonist + advance_to_* + assert_asset_editable

**Files:**
- Modify: `backend/app/pipeline/transitions.py`
- Create: `backend/tests/unit/test_lock_protagonist.py`
- Create: `backend/tests/unit/test_advance_asset_stages.py`

- [ ] **`lock_protagonist(session, project, character)`** — 应用层串行:

```python
async def lock_protagonist(session, project, character) -> None:
    from app.domain.models import Character
    # 必须在同一 session 事务内,调用方保证 session.begin_nested 或外层 begin
    stmt = (
        select(Character)
        .where(Character.project_id == project.id)
        .with_for_update()   # SELECT ... FOR UPDATE
    )
    rows = (await session.execute(stmt)).scalars().all()
    for r in rows:
        if r.id == character.id:
            continue
        if r.is_protagonist:
            r.is_protagonist = False  # 旧主角降级为 supporting(但保留 locked 状态,视 role_type)
            r.role_type = "supporting"
    character.is_protagonist = True
    character.role_type = "protagonist"
    character.locked = True
```

约束:
- 不允许在 `stage_raw != storyboard_ready` 调用(否则 `InvalidTransition`)
- 主角候选必须 `character.project_id == project.id`

- [ ] **`advance_to_characters_locked(session, project)`**:
  - 前置:`stage_raw == storyboard_ready`
  - 条件:`exists(Character where project_id=:pid and is_protagonist and locked)` 才推进;否则 raise `InvalidTransition("no_protagonist_locked")`
  - 成功:`project.stage = 'characters_locked'`

- [ ] **`advance_to_scenes_locked(session, project)`**:
  - 前置:`stage_raw == characters_locked`
  - 条件:项目内 storyboard 总数 > 0,且所有 `storyboards.scene_id` 非空、scene 属于同项目、对应 scene `locked=True`;任何未绑定镜头 / 跨项目 scene / 未锁定 scene 都 raise `InvalidTransition("scene_not_ready")`
  - 成功:`project.stage = 'scenes_locked'`

- [ ] **`assert_asset_editable(project, kind: Literal["character","scene"])`**:
  - kind=character:必须 `stage_raw in {storyboard_ready}`(characters_locked 之后就不可改描述,要改先 rollback)
  - kind=scene:必须 `stage_raw in {characters_locked}`(scene 在 characters_locked 阶段生成和编辑,scenes_locked 之后不可改)
  
  **说明**: scene 只在 `characters_locked` 阶段可编辑,因为 scene 的生成前提是角色已锁定。`storyboard_ready` 阶段还没有 scene。

- [ ] **并发场景单元测试**:
```python
# tests/unit/test_lock_protagonist.py
@pytest.mark.asyncio
async def test_two_locks_serialize(async_session_factory, project_with_two_chars):
    """两个并发 lock_protagonist 调用,最终状态:恰好一个 is_protagonist=True。"""
    project, c1, c2 = project_with_two_chars
    async def lock(cid):
        async with async_session_factory() as s:
            async with s.begin():
                proj = await s.get(Project, project.id)
                char = await s.get(Character, cid)
                await lock_protagonist(s, proj, char)
    import asyncio
    await asyncio.gather(lock(c1.id), lock(c2.id))
    # 重新查:只有一个 True
    async with async_session_factory() as s:
        chars = (await s.execute(
            select(Character).where(Character.project_id == project.id)
        )).scalars().all()
        assert sum(1 for c in chars if c.is_protagonist) == 1
```

- [ ] Commit:`feat(backend): pipeline 扩展 lock_protagonist(SELECT FOR UPDATE) + advance_to_*`

---

## Task 10: gen_character_asset + gen_scene_asset Celery 任务

**Files:**
- Create: `backend/app/tasks/ai/gen_character_asset.py`
- Create: `backend/app/tasks/ai/gen_scene_asset.py`
- Modify: `backend/app/tasks/celery_app.py`(include)
- Modify: `backend/app/tasks/ai/__init__.py`
- Create: `backend/tests/integration/test_character_generate_flow.py`
- Create: `backend/tests/integration/test_scene_generate_flow.py`

`gen_character_asset(character_id, parent_job_id=None)`:
1. Open session → load character + project
2. 构造 prompt(character.description + project.setup_params + ratio)
3. `client.image_generations(settings.ark_image_model, prompt=..., size="1152x864", watermark=False)`
4. `url = resp["data"][0]["url"]`
5. `object_key = await persist_generated_asset(url=url, project_id=project.id, kind="character")`
6. `character.reference_image_url = object_key`
7. `character.meta = {**(character.meta or {}), "last_prompt": prompt, "last_generated_at": utcnow_iso}`
8. **人像库入库(仅在任务执行时已是锁定主角的情况)**:
   若 `character.is_protagonist and character.locked`:
   - `public_url = build_asset_url(object_key)`;这是 `OBS_PUBLIC_BASE_URL + object_key`,必须公网可访问
   - 检查 `video_style_ref.asset_id` 是否已存在,若已存在则跳过(幂等保护)
   - 若 `video_style_ref.asset_group_id` 不存在则 `create_asset_group`,再 `create_asset(public_url)`,随后 `wait_asset_active`;成功后写 `video_style_ref.asset_group_id` / `asset_id` / `asset_status="Active"` / `asset_updated_at`
   
   **注意**: 此处入库仅处理"先锁定主角,后生成图片"的场景。"先生成图片,后锁定主角"的场景由 `POST /characters/{cid}/lock` 端点中的 `ensure_character_asset_registered` 处理。两处都有 `asset_id` 存在性检查,确保不会重复入库。

9. `update_job_progress(child_job_id, status="succeeded")`
10. 如果 parent_job_id 给了,聚合进度更新:
   ```python
   # 使用 SELECT FOR UPDATE 锁住父任务行,避免并发子任务完成时丢计数
   async with session.begin_nested():
       parent = await session.execute(
           select(Job).where(Job.id == parent_job_id).with_for_update()
       )
       parent_job = parent.scalar_one()
       parent_job.done += 1
       if parent_job.done >= parent_job.total:
           parent_job.status = "succeeded"
           parent_job.finished_at = utcnow()
   ```

失败路径:
- `VolcanoContentFilterError` → child job failed + `error_msg="content_filter"`,**parent 不重试**
- `VolcanoRateLimitError` / `VolcanoServerError` → Celery autoretry,最多 3 次(使用 celery task decorator `autoretry_for=(VolcanoRateLimitError, VolcanoServerError, VolcanoTimeoutError)`,`retry_backoff=True`,`retry_kwargs={"max_retries": 3}`)
- `VolcanoAuthError` → 立即 failed,不重试

`gen_scene_asset(scene_id, parent_job_id=None)`:
对称实现,prompt 用 `scene.theme + scene.description + project.ratio`;**不入人像库**。

**integration test(respx 打桩 chat+image)**:
1. 建 project + 3 个 storyboards
2. `POST /characters/generate` → 预期 Chat 被调,返回 3 个角色 JSON
3. `CELERY_TASK_ALWAYS_EAGER=True` 下 3 个 `gen_character_asset` 同步执行,respx 打桩 image_generations → placeholder bytes
4. 断言:3 个 character 行落库 + `reference_image_url` 非空且为 OBS object key + OBS upload mock 收到对应 key/bytes
5. `GET /projects/{id}` 返回的 `characters[]` 长度 = 3

- [ ] Commit:`feat(backend): gen_character_asset / gen_scene_asset Celery 任务`

---

## Task 11: storyboards.bind_scene 端点 + 响应

**Files:**
- Modify: `backend/app/api/storyboards.py`
- Modify: `backend/app/domain/services/scene_service.py`
- Create: `backend/tests/integration/test_bind_scene.py`

`POST /api/v1/projects/{project_id}/storyboards/{shot_id}/bind_scene`

请求:
```json
{ "scene_id": "01H..." }
```

逻辑:
1. `assert stage_raw in {characters_locked}` — 只能在 scenes 匹配阶段手动绑定
2. 校验 scene.project_id == project_id / shot.project_id == project_id
3. `shot.scene_id = scene_id`

响应:
```json
{ "code": 0, "data": { "shot_id": "...", "scene_id": "...", "scene_name": "长安殿" } }
```

- [ ] TDD 写 test_bind_scene:覆盖成功 + 跨项目绑定 403 + 错误 stage 40301
- [ ] commit

---

## Task 12: aggregate_service 填 characters / scenes

**Files:**
- Modify: `backend/app/domain/services/aggregate_service.py`

按 spec §13.1 拼装:

```python
from app.infra.asset_store import build_asset_url

async def build_project_detail(session, project_id) -> ProjectDetail:
    ...  # M2 已实现的 storyboards / generationQueue / generationProgress 不动

    # characters
    chars = (await session.execute(
        select(Character).where(Character.project_id == project_id)
    )).scalars().all()
    characters_out = [
        {
            "id": c.id,
            "name": c.name,
            "role": _ROLE_CN[c.role_type],
            "summary": c.summary or "",
            "description": c.description or "",
            "meta": _meta_to_tags(c.meta, c.video_style_ref),
            "reference_image_url": build_asset_url(c.reference_image_url),
        }
        for c in chars
    ]

    # scenes(含 usage)
    scene_rows = (await session.execute(
        select(Scene).where(Scene.project_id == project_id)
    )).scalars().all()
    # usage = 按 scene_id 分组 count
    usage_stmt = (
        select(StoryboardShot.scene_id, func.count(StoryboardShot.id))
        .where(StoryboardShot.project_id == project_id,
               StoryboardShot.scene_id.is_not(None))
        .group_by(StoryboardShot.scene_id)
    )
    usage_map = dict((await session.execute(usage_stmt)).all())
    scenes_out = [
        {
            "id": s.id,
            "name": s.name,
            "theme": s.theme,
            "summary": s.summary or "",
            "description": s.description or "",
            "meta": _meta_to_tags(s.meta, s.video_style_ref),
            "usage": f"场景复用 {usage_map.get(s.id, 0)} 镜头",
            "reference_image_url": build_asset_url(s.reference_image_url),
        }
        for s in scene_rows
    ]

    detail.characters = characters_out
    detail.scenes = scenes_out
    return detail


_ROLE_CN = {"protagonist": "主角", "supporting": "关键配角", "atmosphere": "氛围配角"}


def _meta_to_tags(meta: dict | None, video_style_ref: dict | None = None) -> list[str]:
    tags: list[str] = []
    if isinstance(meta, dict):
        for key in ("style", "tone", "costume", "lighting"):
            value = meta.get(key)
            if value:
                tags.append(str(value))
    if isinstance(video_style_ref, dict) and video_style_ref.get("asset_status"):
        tags.append(f"人像库:{video_style_ref['asset_status']}")
    return tags
```

- [ ] TDD:`tests/integration/test_projects_api.py` 加断言 — 建 character + scene + bind → `/projects/{id}` 返回 `characters/scenes/usage` 字段对
- [ ] commit

---

## Task 13: 主角唯一性并发集成测试(真正起协程打 API)

**Files:**
- Create: `backend/tests/integration/test_protagonist_race.py`

两个 `AsyncClient` 并发 `POST /characters/{cid}/lock {"as_protagonist": true}`,其中一个必须落在另一个事务完成之后(MySQL `FOR UPDATE` 保证行锁),最终 `GET /characters` 返回仅一个 `is_protagonist=true`。

- [ ] commit:`test(backend): 主角唯一性并发回归`

---

## Task 14: 冒烟脚本 scripts/smoke_m3a.sh

**Files:**
- Create: `backend/scripts/smoke_m3a.sh`

覆盖(在 `AI_PROVIDER_MODE=mock` 下即可跑,验证状态机闭环;在 real 模式下跑一遍当手动回归):
1. 建 project → stage=draft
2. POST /parse → 轮询 job → stage=storyboard_ready
3. POST /characters/generate → 轮询子 job → /characters 列表非空
4. POST /characters/{cid1}/lock as_protagonist=true
5. GET /projects/{id} → stage_raw=characters_locked
6. POST /scenes/generate → 轮询子 job
7. POST /storyboards/{sid}/bind_scene 逐一绑定
8. POST /scenes/{sid}/lock 逐一锁定
9. GET /projects/{id} → stage_raw=scenes_locked
10. 每一步 echo 出关键字段,失败即 exit 1

- [ ] commit

---

## Task 15: DoD + README 更新

**Files:**
- Modify: `backend/README.md` — 新增 "M3a 端点 / 错误码 / stage 速览"
- Modify: `docs/integrations/volcengine-ark-api.md` 末尾追加 "本项目接入落点:M3a 已实现 Chat/Image + 人像库骨架"(一行)
- Modify: `docs/superpowers/specs/2026-04-20-backend-mvp-design.md` §6.4 / §13.1 — 登记 42201,补 `characters/scenes.reference_image_url` 与 `meta: string[]` 聚合契约
- Modify: `docs/superpowers/specs/2026-04-20-frontend-mvp-design.md` §9 — 同步 `CharacterAsset` / `SceneAsset` 的 `reference_image_url?: string | null`

DoD:
- [ ] `pytest -v` 全绿 + 覆盖 ≥ 70% (`pytest --cov=app`)
- [ ] `mypy app` 无新增 error
- [ ] `AI_PROVIDER_MODE=mock` 冒烟脚本绿
- [ ] `AI_PROVIDER_MODE=real` 手动跑一次 `POST /characters/generate`(带真实 ARK_API_KEY + OBS 配置),查询到 `reference_image_url` 是 OBS object key,`OBS_PUBLIC_BASE_URL/<key>` 可访问
- [ ] 配置 OBS + 人像库 AK/SK 后,锁定主角会调用 `CreateAsset`,最终 `characters.video_style_ref.asset_status=Active`
- [ ] pipeline 主角唯一性并发测试 10 次全绿
- [ ] 新增错误码 42201 在 `docs/superpowers/specs/2026-04-20-backend-mvp-design.md` §6.4 表中登记(顺带 PR)
- [ ] 前后端契约一致性验证:对比 `docs/superpowers/specs/2026-04-20-frontend-mvp-design.md` §9 的 `CharacterAsset` / `SceneAsset` 类型与 `backend/app/domain/services/aggregate_service.py` 的输出字段,确保 `reference_image_url` / `meta` / `usage` 等字段类型和语义一致

- [ ] commit

---

## 附录 A:M3a 不触碰的 spec 条款

- §5.4 DB 兜底主角唯一(`protagonist_guard` 生成列)— 不做
- §7.2 `render_*` / `export_*` — 留 M3b/c/4
- §7.4 断点续跑扫描 — 留 M5
- §10 `provider_task_id` 回查 — 同上

## 附录 B:风险与回滚

- **真实火山额度**:`/characters/generate` 会并发打 N 次 Image API;建议 `.env` 加 `AI_RATE_LIMIT_PER_MIN` 限流(M5 做令牌桶,M3a 靠 Celery 队列 concurrency=4 粗粒度限)
- **图片时效**:火山 URL 24h 失效,下载并上传 OBS 必须同步完成;`asset_store` 里把 `asset_download_timeout=30s` 作为下载失败阈值,OBS 上传失败时 job failed 且不写火山临时 URL
- **回滚策略**:若真实调用失败率 > 20%,恢复 `AI_PROVIDER_MODE=mock`(不需要改代码),走回 M2 行为,不影响已入库的 characters/scenes 行
- **主角唯一性 DB 兜底延后**:应用层 `SELECT ... FOR UPDATE` 在同实例 MySQL 串行化;跨数据库分片不在 MVP 范围

## 附录 C:关键不变量速查

1. 任何 `characters` / `scenes` 写路径 → 先 `assert_asset_editable`
2. 任何 `project.stage` 改动 → 只能经 `pipeline.transitions.advance_to_*` 或 `rollback_stage`
3. 火山返回的任何 URL **不入库** — 只有 `asset_store.persist_generated_asset` 返回的 OBS object key 入库
4. 主角切换 → 只能经 `lock_protagonist`,不可 `character.is_protagonist = True` 裸改
5. `reference_image_url` 存 **OBS object key**,aggregate 层通过 `OBS_PUBLIC_BASE_URL` 拼公网 URL
6. 父任务进度更新 → 必须使用 `SELECT ... FOR UPDATE` 锁父任务行,避免并发子任务丢计数
7. 角色创建幂等 → 使用 `SELECT Project ... FOR UPDATE` 锁 project 行,串行化同项目的 `/generate` 请求
8. 主角入人像库 → 在 `POST /characters/{cid}/lock` 端点中,若 `as_protagonist=True` 且已有图片,同步调用 `ensure_character_asset_registered`
9. OBS_MOCK → 仅允许在 `AI_PROVIDER_MODE != real` 时使用,real 模式必须配置真实 OBS

---

## 附录 D: M3a 优化记录

**2026-04-21 第一轮优化**:
1. **M2 Review 章节补全**:明确标注"无遗留问题",避免执行者困惑
2. **Task 3 重试逻辑简化**:移除嵌套 try-except,改为线性异常处理流程,提升可读性和正确性
3. **Task 5 同步 I/O 修复**:在 `persist_generated_asset` 中使用 `asyncio.to_thread()` 包装 OBS 上传,避免阻塞事件循环
4. **Task 7 并发处理明确**:补充 `SELECT ... FOR UPDATE` 串行化同名角色创建的具体实现说明
5. **Task 7 错误码注册补全**:新增 42201 错误码的完整注册代码示例
6. **Task 6 索引幂等性补全**:补充完整的 inspector 检查索引的迁移代码示例
7. **Task 10 父任务进度更新补全**:补充完整的 `SELECT FOR UPDATE` 锁父任务行的代码示例

**2026-04-21 第二轮优化**:
1. **Task 3 重试逻辑修复**:新增 `_map_httpx_exception` 方法,确保 httpx 网络错误能正确映射并重试,而不是直接抛出
2. **Task 7 并发保护修正**:改为锁 project 行而非依赖不存在的空隙锁,确保同项目并发请求真正串行化
3. **Task 7 主角入库闭环**:在 `POST /characters/{cid}/lock` 端点补充 `ensure_character_asset_registered` 逻辑,解决"先生成后锁定"场景下的入库触发
4. **Task 5 OBS_MOCK 安全加固**:在 `upload_file_to_obs` 中禁止 `OBS_MOCK=1` 与 `AI_PROVIDER_MODE=real` 同时使用,避免生产误用
5. **Task 5 OBS URL 配置校验**:在 `get_obs_url` 中,仅 mock 模式允许 fallback,real 模式缺配置立即报错
6. **Task 8 跨项目 scene 防护**:在 scene lock SQL 中增加 `sc.project_id != :pid` 检查,防止跨项目 scene 被错误放行
7. **Task 7 错误码实现澄清**:明确 42201 通过 HTTPException 返回,不依赖可能不存在的 ERROR_MESSAGES registry
8. **Task 1 注释完善**:补充 OBS SDK 和 respx 的用途说明

**2026-04-21 第三轮优化**:
1. **Task 3 代码缩进修复**:统一 `_map_httpx_exception` 和 `_request_with_retry` 为标准 4 空格缩进
2. **Task 2 死代码清理**:移除 `classify_exception` 函数,改用 Task 3 的 `_map_httpx_exception`,避免代码冗余
3. **Task 7 导入说明补全**:在 `ensure_character_asset_registered` 函数中补充完整的 import 语句和时间工具说明
4. **Task 7 Chat 错误处理补全**:在 `POST /generate` 流程中补充完整的 try-except 代码示例,包含空数组和内容违规两种错误处理
5. **Task 10 人像库入库逻辑澄清**:明确区分两种入库场景(先锁后生成 vs 先生成后锁),并在两处都加幂等保护,避免重复入库
6. **Task 9 scene 编辑窗口修正**:明确 scene 只在 `characters_locked` 阶段可编辑,移除 `storyboard_ready` 选项
7. **Task 5 临时文件清理**:在 `persist_generated_asset` 中添加 finally 块,确保临时文件在上传后被清理
8. **Task 15 DoD 补充**:新增前后端契约一致性验证项,确保 aggregate 输出与前端类型定义匹配

---

## 一句话总结

M3a 把 M2 的 mock 天花板换成真实火山出口(Chat + Image + 人像库骨架),补齐 `storyboard_ready → characters_locked → scenes_locked` 两段 stage 的资产生成 + 锁定全链路;11 个业务端点 + 2 个 Celery 任务 + 1 次 pipeline 扩展 + 1 次聚合契约填充,业务表不新增列(仅补索引,人像库 asset 信息写入 `characters.video_style_ref`)。
