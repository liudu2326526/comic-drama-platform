# Comic Drama Frontend (M1)

Vue 3 + Vite + TS + Pinia + Axios 工程骨架, 联调后端 M1 的项目 CRUD 与 rollback 端点。

## 快速开始

```bash
# 0. 确保后端 M1 已启动在 http://127.0.0.1:8000
# 1. 安装依赖
cd frontend && npm install

# 2. 日常启动 dev (代理 /api -> 127.0.0.1:8000)
npm run dev
# 访问 http://127.0.0.1:5173

# 3. 冒烟 (从 repo 根目录执行; 脚本会自行启动/清理 dev server)
# 注意: 冒烟不需要先执行 npm run dev; 若 5173 已被手动 dev 占用, 请先停止
./frontend/scripts/smoke_m1.sh
```

## 测试

```bash
npm run test         # 纯逻辑单测 (error / useJobPolling / useStageGate)
npm run typecheck    # vue-tsc 全量类型检查
npm run build        # 构建产物到 dist/
```

## M1 已交付

- 脚手架: Vite + Vue 3 + TS + Router + Pinia + Axios
- 样式: 迁移自 `product/workbench-demo/`, 按 variables/global/panels 三分
- `projects` 列表 / 详情 / 创建 / 删除联调 OK
- `/rollback` 联调 OK, 含非法回退的 40301 toast 映射
- `useJobPolling` / `useStageGate` 骨架 + 单测, 为 M2 留接口

## M1 不包含

- 分镜解析、角色/场景资产、镜头渲染、导出 — 见 M2+
- 真实 AI job 轮询 — useJobPolling 目前只对着 mock fetcher 跑单测
- 登录鉴权 / i18n / 主题切换 — MVP 范围外

## M2 范围

M2 在 M1 的项目 CRUD 之上打通了 AI 解析 + 分镜编辑链路。

### 新增端点对接

| 端点 | 组件 / Store |
| --- | --- |
| `POST /api/v1/projects/{id}/parse` | `ProjectCreateView`(开始拆分分镜按钮)/ `ProjectSetupPanel`(空态大按钮) |
| `GET /api/v1/jobs/{id}` | `useJobPolling` → `ProjectSetupPanel` 真实轮询 |
| `GET /api/v1/projects/{id}/storyboards` | 读路径仍由 `GET /projects/{id}` 聚合,M2 未单独使用 |
| `POST /api/v1/projects/{id}/storyboards` | `StoryboardPanel` 新增镜头 |
| `PATCH /api/v1/projects/{id}/storyboards/{shot_id}` | `StoryboardPanel` 编辑镜头 |
| `DELETE /api/v1/projects/{id}/storyboards/{shot_id}` | `StoryboardPanel` 删除镜头 |
| `POST /api/v1/projects/{id}/storyboards/reorder` | `StoryboardPanel` 上移/下移 |
| `POST /api/v1/projects/{id}/storyboards/confirm` | `StoryboardPanel` 顶部"确认 N 镜头" |

### 本地联调

```bash
# 1) 启动后端(务必 EAGER 模式,mock VolcanoClient 当场跑完)
cd backend && CELERY_TASK_ALWAYS_EAGER=true uvicorn app.main:app --reload

# 2) 启动前端
cd frontend && pnpm dev

# 3) 冒烟
./frontend/scripts/smoke_m2.sh
```

### 阶段门(useStageGate)在 M2 的生效点

- 分镜编辑窗口: `stage_raw ∈ {draft, storyboard_ready}`; 其他 stage 下所有写按钮灰化并悬浮提示 "当前阶段已锁定,如需修改请 回退阶段"
- 点击被锁定的写按钮或后端返回 40301 时,顶栏 toast 附带 "回退阶段" 快捷入口,打开 `StageRollbackModal`

### M2 不包含

- 角色 / 场景资产生成、镜头渲染、导出(M3a+)
- 分镜拖拽排序(使用 ↑ ↓ 按钮;拖拽进 M3a+)
- 分镜 `duration_sec` 批量调整(M3c+)

## M3a 范围

M3a 在 M2 的分镜闭环之上,打通了"生成角色 → 锁定主角 → 生成场景 → 绑定镜头 → 锁定场景"的资产链路。

### 新增端点对接

| 端点 | 组件 / Store |
| --- | --- |
| `GET /api/v1/projects/{id}/characters` | 调试/备用端点;页面读路径仍走聚合 `GET /projects/{id}` |
| `POST /api/v1/projects/{id}/characters/generate` | `CharacterAssetsPanel`(空态大按钮)+ `store.generateCharacters`; 返回 `extract_characters` 主 job,前端在其成功后自动续接 `gen_character_asset` 主 job |
| `PATCH /api/v1/projects/{id}/characters/{cid}` | `CharacterEditorModal` + `store.patchCharacter` |
| `POST /api/v1/projects/{id}/characters/{cid}/regenerate` | `CharacterAssetsPanel` "重新生成参考图" |
| `POST /api/v1/projects/{id}/characters/{cid}/lock` | `CharacterAssetsPanel` "设为主角 · 锁定" / "仅锁定" |
| `POST /api/v1/projects/{id}/scenes/generate` | `SceneAssetsPanel`(空态大按钮) |
| `PATCH /api/v1/projects/{id}/scenes/{sid}` | `SceneEditorModal` |
| `POST /api/v1/projects/{id}/scenes/{sid}/regenerate` | `SceneAssetsPanel` "重新生成参考图" |
| `POST /api/v1/projects/{id}/scenes/{sid}/lock` | `SceneAssetsPanel` "锁定场景" |
| `POST /api/v1/projects/{id}/storyboards/{shot_id}/bind_scene` | `SceneAssetsPanel` "绑定当前选中镜头" |

### Visual style reference UI

Character and scene setup pages render `StyleReferenceCard` next to `PromptProfileCard`.
Character detail views show full-body and headshot images; scene detail views label generated scene images as no-person references.

### 阶段门

| 操作 | 允许的 `stage_raw` |
| --- | --- |
| 生成/编辑/锁定角色 | `storyboard_ready` |
| 生成/编辑/绑定/锁定场景 | `characters_locked` |

所有被阶段门拦截的写按钮会 toast + 弹 `StageRollbackModal`。

### 新增错误码映射

| code | 文案 |
| --- | --- |
| 42201 | AI 内容违规,请修改文案后重试 |

### 本地联调

```bash
# 1) 后端(mock + EAGER)
cd backend && AI_PROVIDER_MODE=mock CELERY_TASK_ALWAYS_EAGER=true uvicorn app.main:app --reload

# 2) 前端
cd frontend && npm run dev

# 3) 冒烟
./frontend/scripts/smoke_m3a.sh
```

### M3a 不包含

- 镜头渲染、render 版本历史(M3b/c)
- 导出(M4)
- 手动新增角色 / 场景(后端无对应 POST 端点,demo 占位按钮保持 disabled)
- 分镜拖拽绑定场景(用"当前选中镜头 → 此场景"按钮;拖拽 M3b+)
- 主角人像库专用进度条(通过 `meta` 里的 "人像库:Active" 文本体现)

## M3b 单镜头渲染

M3b 前端新增：

- `src/api/shots.ts`
- `GenerationPanel` 先拿草稿、允许编辑 prompt / references、确认后生成
- `RenderVersionHistory` 历史版本切换
- 单镜头 `render_shot` job 轮询与刷新恢复
- 场景详情暂时保留手动“绑定镜头 → 此场景”入口，作为进入 `scenes_locked` 的过渡能力

联调前置：

1. 后端已合入 `docs/superpowers/plans/2026-04-22-backend-m3b-render-shot.md`
2. 项目已至少推进到 `scenes_locked`
3. 本地后端运行在 `127.0.0.1:8000`

冒烟：

```bash
cd frontend
chmod +x scripts/smoke_m3b.sh
PID=<已有 scenes_locked 项目 id> ./scripts/smoke_m3b.sh
```

## 目录

`src/api/` 请求封装 · `src/store/` Pinia · `src/composables/` 无状态逻辑 ·
`src/views/` 页面 · `src/components/{layout,common,setup,storyboard,character,scene,generation,export,workflow}/` 业务组件 ·
`src/styles/` 全局样式 · `tests/unit/` 单测
