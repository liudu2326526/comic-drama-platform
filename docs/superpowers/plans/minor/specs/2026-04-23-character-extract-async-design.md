# 角色提取异步化与生成进度串联设计

> 文档版本: v0.1 · 2026-04-23
> 范围: 小版本改动
> 目标系统: `backend/` + `frontend/` 的角色生成链路

---

## 1. 背景

当前 `POST /api/v1/projects/{id}/characters/generate` 在返回 `job_id` 前,会先同步调用一次 Ark Chat 做角色提取。这个设计带来两个问题:

1. HTTP 请求并不是真正“立即 ack”,当 Ark 首次请求超时且触发重试时,前端 60 秒 timeout 会先报错,但后端后续仍可能成功创建角色与图片任务。
2. 前端进度条只能看到 `gen_character_asset` 主 job,看不到“角色提取”这段最慢且最容易误判失败的阶段。

这次改动的目标是把“角色提取”也纳入异步任务体系,并把“提取角色 → 生成参考图”串成一条连续可恢复的角色生成进度。

## 2. 目标与非目标

### 2.1 目标

- `POST /characters/generate` 改成真正的立即 ack,HTTP 请求不再等待 LLM 角色提取完成。
- 新增独立的 `extract_characters` job,由 Celery 执行角色提取与角色落库。
- `extract_characters` 成功后,后端自动创建并分发第二段 `gen_character_asset` 主 job 和 N 个 `gen_character_asset_single` 子 job。
- 前端把两段 job 串联成一个连续进度条,至少能明确展示:
  - `正在提取角色…`
  - `正在生成角色… X/Y`
- 页面刷新后,store 能恢复当前正在进行的角色提取或角色生成任务。
- 清理“请求超时后其实成功,但失败 banner 仍残留”的错误态。

### 2.2 非目标

- 不改角色图片生成子任务的并发策略。
- 不新增“单独重试角色提取”入口;仍复用 `生成角色资产` 主按钮。
- 不改角色锁定、人像库注册流程。
- 不把场景生成链路一并改造;本次只处理 characters。

## 3. 推荐方案

采用“两段主 job 串联”方案:

1. `extract_characters`
   - 负责读取项目正文、调用 Ark Chat 提取角色 JSON、解析结果、幂等创建/更新 `characters` 行。
2. `gen_character_asset`
   - 负责承接上一步创建好的角色,再分发 N 个 `gen_character_asset_single` 子 job 做图片生成。

`POST /characters/generate` 只负责创建第一段 job 并立即返回。前端收到第一个 `job_id` 后开始轮询。当 `extract_characters` 成功时,如果 `job.result.next_job_id` 存在,则自动切换到第二段 `gen_character_asset` 继续轮询。

这样能把“角色提取慢”和“角色出图慢”区分开,同时不需要用户理解两个入口。

## 4. 后端设计

### 4.1 Job Kind

`jobs.kind` 新增:

- `extract_characters`

迁移策略:

- 不修改已存在的历史 Alembic revision
- 新增一个以当前 head 为 `down_revision` 的 revision,只负责把 `extract_characters` 加进 `jobs.kind` 的 ENUM

语义:

- 主 job,只负责“角色提取 + 角色落库 + 创建后续角色图片任务”。
- 终态时通过 `result` 告知前端后续主 job:
  - `next_job_id`
  - `next_kind`
  - `character_ids`

### 4.2 API 行为

`POST /api/v1/projects/{project_id}/characters/generate`

调整后行为:

1. 校验 `project` 存在且 `stage_raw == storyboard_ready`
2. 创建 `extract_characters` job,状态初始为 `queued`
3. `commit`
4. 分发 Celery `extract_characters.delay(project_id, job_id)`
5. 立即返回 `GenerateJobAck { job_id, sub_job_ids: [] }`

关键变化:

- HTTP 层不再同步调用 `volcano_client.chat_completions`
- 这样前端拿到 ack 的时间稳定在毫秒级

### 4.3 新任务 `extract_characters`

新建 `backend/app/tasks/ai/extract_characters.py`,处理 4 个阶段:

1. `读取项目与校验阶段`
2. `调用 Ark 提取角色`
3. `解析并幂等落库 Character`
4. `创建并分发 gen_character_asset 主 job + 子 job`

推荐进度映射:

- 10: 已读取项目
- 45: LLM 返回成功
- 70: Character 行落库完成
- 100: 后续 `gen_character_asset` 主 job 已创建并成功分发

补充约束:

- `extract_characters` 用 `progress` 表达阶段式进度,`total` 保持 `null`
- 不使用 `done=4 / total=4` 这种“阶段数冒充总任务数”的表达

终态 `result` 示例:

```json
{
  "next_job_id": "01K...",
  "next_kind": "gen_character_asset",
  "character_ids": ["01K...", "01K..."]
}
```

失败时:

- 写 `status="failed"`
- `error_msg` 使用可读业务错误,例如 `未识别到角色` / `AI 内容违规` / `dispatch failed: ...`
- 整个 task 必须有顶层 `try/except`,确保任何异常都会把 job 写成 `failed`

### 4.4 `gen_character_asset` 保持主 job 聚合

现有 `gen_character_asset` 和 `gen_character_asset_single` 结构保留,但其创建位置从 HTTP 路由挪到 `extract_characters` task 中。

`gen_character_asset` 的语义保持:

- `total = 角色数`
- `done = 已完成图片生成的角色数`
- `progress = done / total * 100`

这样前端第二段进度条可以继续复用当前实现。

分发失败收口:

- 如果 `extract_characters` 已创建了 `gen_character_asset` 主 job 和部分子 job,但在 dispatch child tasks 时发生 broker 异常,则需要把:
  - `extract_characters` 标记为 `failed`
  - 新创建的 `gen_character_asset` 主 job 一并标记为 `failed`
- 不允许留下“第一段 failed,第二段仍 running”的僵尸态

### 4.5 幂等与并发

后端仍需在 `storyboard_ready` 阶段限制“同时只能存在一个角色生成链路主任务”。

推荐查重策略:

- 若项目下存在 `extract_characters` 或 `gen_character_asset` 的 `queued/running` job,则 `POST /characters/generate` 返回 `40901`

并发说明:

- 主要依赖 `SELECT ... FOR UPDATE` 锁住 `projects` 行来串行化同一项目的重复点击
- 本次不额外引入 `jobs` 表唯一索引,但实现与文档都要明确并发保护依赖的是项目行锁

这样能避免:

- 用户重复点击
- 页面超时后再次触发
- 两条角色生成链路同时写同一批角色

## 5. 前端设计

### 5.1 Store 任务跟踪

现有 `generateCharactersJob` 继续保留为“当前活跃角色生成主 job”,但它不再只代表 `gen_character_asset`,而是代表以下任一 job:

- `extract_characters`
- `gen_character_asset`

恢复逻辑顺序改为:

1. 优先找 `extract_characters` 的 `queued/running`
2. 找不到再找 `gen_character_asset` 的 `queued/running`
3. 两者都没有时,才读取最近失败 job

同时补一个错误清理规则:

- 如果当前项目已有角色数据,且不存在失败中的角色生成主 job,则清空 `generateCharactersError`

### 5.2 进度条文案

`CharacterAssetsPanel` 的主 banner 根据当前 job.kind 切换:

- `extract_characters`
  - 文案: `正在提取角色…`
  - 进度: 直接显示 job.progress
- `gen_character_asset`
  - 文案: `正在生成角色… done/total`
  - 进度: 用现有 `done/total` 或 `progress`

失败文案也按 `kind` 区分:

- `extract_characters` 失败: `角色提取失败: ...`
- `gen_character_asset` 失败: `角色出图失败: ...`

### 5.3 串联轮询

当 `useJobPolling(activeGenerateCharactersJobId)` 轮询到:

- `extract_characters.status === succeeded`
- 且 `job.result.next_job_id` 存在

则不要立刻 toast “角色已生成”,而是:

1. 把 store 当前活跃 job 切换为 `next_job_id`
2. 继续轮询第二段 `gen_character_asset`

只有第二段主 job `gen_character_asset` 成功时,才:

1. `reload()`
2. 清空错误态
3. toast `角色已生成`

### 5.4 超时残留错误修正

如果第一次 `POST /characters/generate` 因浏览器 timeout 失败,但实际上后端已成功创建 `extract_characters` job,前端在刷新或 reload 后应通过恢复逻辑重新挂上该 job,并覆盖掉旧的 `generateCharactersError`。

这意味着:

- `findAndTrackActiveJobs()` 在发现运行中 job 时,必须先清掉旧的 `generateCharactersError`
- `load()` / `reload()` 后角色列表非空时,不能继续无条件保留上一次本地 timeout 文案
- 需要补一条专门的前端单测,验证“已有 timeout 错误 → 恢复到运行中的 extract job 后错误被清掉”

## 6. 数据契约

### 6.1 `GET /jobs/{id}`

前端需要依赖现有 `JobState.result` 读取后续 job 信息。因此 `extract_characters` 终态时的 `result` 必须稳定返回:

```json
{
  "next_job_id": "01KPW...",
  "next_kind": "gen_character_asset",
  "character_ids": ["01K...", "01K..."]
}
```

前端类型建议:

- `next_kind` 用字面量联合类型 `"gen_character_asset" | null`,而不是宽泛 `string`

### 6.2 `ProjectData.generationQueue`

不强制改变聚合契约。角色面板继续以 `GET /jobs/{id}` 轮询主 job 为主,`generationQueue` 只作为项目详情背景信息。

## 7. 风险与应对

### 风险 1: `extract_characters` 成功,但 `gen_character_asset` 分发失败

应对:

- `extract_characters` 直接标记 `failed`
- `error_msg` 明确写为 `dispatch failed: ...`
- 同时把已创建的 `gen_character_asset` 主 job 标记为 `failed`
- 不返回半成功态给前端

### 风险 2: 页面刷新时同时存在旧失败 job 和新运行中 job

应对:

- 恢复逻辑优先运行中 job
- 运行中 job 一旦命中,立即清空 `generateCharactersError`

### 风险 3: LLM 返回空数组或 JSON 结构异常

应对:

- `extract_characters` 统一转成业务错误:
  - `未识别到角色`
  - `AI 内容违规`
  - `AI 提取失败: ...`

## 8. 测试策略

后端:

- 单测 `extract_characters` 的主路径、空结果、内容过滤、dispatch 失败
- 集成测试 `POST /characters/generate` 必须立即返回 ack,不再依赖同步 LLM 完成
- 回归测试 `gen_character_asset` 聚合进度仍正确
- 迁移测试需覆盖新 revision 能把 `extract_characters` 正确加进 `jobs.kind` ENUM

前端:

- store 恢复逻辑优先跟踪 `extract_characters`
- `CharacterAssetsPanel` 在 `extract_characters -> gen_character_asset` 串联时,进度 banner 文案正确切换
- 当 `extract_characters` 成功且 `next_job_id` 存在时,不会提前 toast 成功
- 旧 timeout 错误在 reload 后可被运行中 job 覆盖清除
- `extract_characters` 失败与 `gen_character_asset` 失败使用不同 banner / toast 文案

## 9. 落地结果

改造完成后,用户看到的链路会变成:

1. 点击“生成角色资产”
2. 立刻进入 `正在提取角色…`
3. 提取完成后自动切换到 `正在生成角色… X/Y`
4. 全部完成后显示角色列表和参考图

不会再出现“前端 60 秒 timeout 先报错,后端几秒后其实成功”的误导性体验。
