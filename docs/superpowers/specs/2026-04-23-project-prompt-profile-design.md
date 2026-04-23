# 漫剧生成平台 — 项目级统一背景提示词设计文档

> **文档版本**: v1.0 · 2026-04-23
> **范围**: 角色设定 / 场景设定中的项目级统一背景提示词
> **配套**:
> - 后端设计: `docs/superpowers/specs/2026-04-20-backend-mvp-design.md`
> - 前端设计: `docs/superpowers/specs/2026-04-20-frontend-mvp-design.md`
> - 当前工作台界面: `frontend/src/components/character/CharacterAssetsPanel.vue`、`frontend/src/components/scene/SceneAssetsPanel.vue`

---

## 1. 目标与非目标

### 1.1 目标

- 为每个项目新增两份可选的项目级统一背景提示词配置:
  - 角色统一背景提示词
  - 场景统一背景提示词
- 配置采用两阶段工作流:
  - 先生成或编辑配置草稿
  - 用户确认后,再触发具体角色图或场景图生成
- 已确认配置在后续每个角色/场景出图时自动拼入 prompt,提升同项目内视觉一致性
- 若用户从未创建配置,系统保持现有行为,不阻塞流程也不附加额外 prompt
- 保持现有异步任务模型: HTTP 只返回 ack,实际生成仍由 Celery job 执行

### 1.2 非目标

- 不新增新的 `project.stage`
- 不强制用户必须创建或确认背景提示词后才能继续流程
- 不在首版引入复杂 prompt 结构编辑器(如负向提示词、多段标签、权重参数)
- 不在首版自动重生成所有已生成资产;只有用户在“确认并生成”时才触发后续生成
- 不修改镜头渲染(`render_shot`)的 prompt 结构;本期仅覆盖角色图与场景图生成

---

## 2. 产品定义

### 2.1 核心概念

项目级统一背景提示词是项目层面的“风格与环境约束”,不是单个角色/场景记录自身的描述字段。

本期一个项目有两套独立配置:

- `character prompt profile`: 用于角色参考图生成
- `scene prompt profile`: 用于场景参考图生成

两套配置各自维护,互不影响。

### 2.2 双版本语义

每套配置都同时存在两个版本位:

- `draft`: 当前草稿,可由 AI 生成或用户手改
- `applied`: 最近一次已确认应用的版本

系统行为规则:

- 生成具体角色/场景资产时,只读取 `applied`
- 编辑器里展示和修改的是 `draft`
- 若 `draft` 为空,用户不能执行“确认并生成”
- 若 `applied` 为空,表示当前项目尚未启用该类统一提示词
- 若 `draft` 与 `applied` 不同,界面需明确提示“当前生成仍使用上次确认版本”

### 2.3 可选性规则

统一背景提示词是可选能力,不是强制门槛。

- 用户未创建配置:
  - 角色生成沿用现有角色 prompt
  - 场景生成沿用现有场景 prompt
- 用户创建了草稿但未确认:
  - 后续生成仍不使用草稿
- 用户确认后:
  - 该类型后续生成都自动拼入对应 `applied.prompt`

---

## 3. 用户流程

### 3.1 角色统一背景提示词

入口位于角色设定面板顶部,即当前“新增角色资产”按钮左侧的大块预留区。

用户路径:

1. 用户进入角色设定页(`stage_raw = storyboard_ready`)
2. 顶部看到“统一背景提示词”配置区
3. 用户可选择:
   - `AI 生成建议`
   - 手动输入草稿
   - 跳过,直接按现有方式生成角色
4. 若已有草稿,用户可:
   - 编辑草稿
   - 重新 AI 生成草稿
   - 确认并生成角色资产
5. 用户点击“确认并生成角色资产”后:
   - 后端将 `draft` 复制到 `applied`
   - 然后触发现有角色生成链路或“批量重生成未锁定角色”链路

### 3.2 场景统一背景提示词

入口位于场景设定面板顶部,即当前“新增场景资产”按钮左侧的大块预留区。

用户路径与角色侧一致,但阶段与触发链路切换为场景侧:

1. 用户进入场景设定页(`stage_raw = characters_locked`)
2. 用户生成或编辑场景统一背景提示词草稿
3. 用户点击“确认并生成场景资产”后:
   - 后端将 `draft` 复制到 `applied`
   - 然后触发现有场景生成链路或“批量重生成未锁定场景”链路

### 3.3 典型状态

每个配置区有 4 个稳定 UI 状态:

- `未创建`: draft/applied 都为空
- `草稿中`: draft 有值, applied 为空
- `已应用`: draft 与 applied 相同
- `已修改未应用`: draft 与 applied 都有值,但内容不同

---

## 4. 推荐方案与取舍

### 4.1 方案对比

**方案 A: 只加两个项目级文本字段**

- `project.character_prompt`
- `project.scene_prompt`

优点:

- 实现最简单

缺点:

- 无法表达“两阶段确认”语义
- 无法区分“草稿已改但未生效”
- 后续扩展负向提示词/标签时需要重构

**方案 B: 项目级 prompt profile,首版只暴露一个核心 `prompt` 字段**

优点:

- 支持 `draft/applied` 双版本
- 与“两阶段生成”完全对齐
- 后续扩字段不需要再改接口形态

缺点:

- 首版模型与接口略多

**方案 C: 把统一提示词只放在 `/characters/generate` 和 `/scenes/generate` 请求体**

优点:

- 看起来不需要改项目模型

缺点:

- 无法在刷新页面后恢复
- 无法支持“先改草稿,再确认应用”
- 与项目级配置的产品语义不一致

### 4.2 结论

采用 **方案 B**。

实现原则:

- 资源归属项目
- 首版 profile 结构轻量
- 任务链路只读取 `applied`
- 前端只编辑 `draft`

---

## 5. 数据模型设计

### 5.1 项目表新增字段

在 `projects` 表新增 4 个 JSON 字段:

- `character_prompt_profile_draft`
- `character_prompt_profile_applied`
- `scene_prompt_profile_draft`
- `scene_prompt_profile_applied`

推荐直接挂在 `Project` 模型上,不新建独立表。原因:

- 首版仅 2 类配置,规模固定
- 总是按项目详情一起读取,不需要单独分页/筛选
- 避免为了很轻的资源引入额外 join 和 service 复杂度

### 5.2 JSON 结构

首版统一结构:

```json
{
  "prompt": "统一的古风宫廷阴雨氛围,冷青色调,写实电影质感,服装纹理清晰,光线克制",
  "source": "ai"
}
```

字段说明:

- `prompt: string`
  - 真正参与拼装的文本
  - 必填,去首尾空白后不能为空
- `source: "ai" | "manual"`
  - 用于前端提示“由 AI 生成”或“手动编辑”
  - 不参与生成逻辑

### 5.3 扩展约束

虽然首版只开放 `prompt`,但字段形态保留 JSON,以便后续扩展:

- `negative_prompt`
- `style_tags`
- `version_note`
- `last_generated_job_id`

首版不落这些字段,但接口和类型命名不要把资源锁死成“纯字符串”。

---

## 6. 后端接口设计

### 6.1 返回形态

新增接口均沿用现有 envelope:

```json
{
  "code": 0,
  "message": "success",
  "data": ...
}
```

### 6.2 资源读取

`GET /projects/{project_id}` 的聚合详情中新增两个字段:

- `characterPromptProfile`
- `scenePromptProfile`

推荐响应结构:

```json
{
  "draft": { "prompt": "...", "source": "ai" },
  "applied": { "prompt": "...", "source": "ai" },
  "status": "dirty"
}
```

其中 `status` 为后端派生展示值:

- `empty`
- `draft_only`
- `applied`
- `dirty`

这样前端无需自行比对 JSON 再判断状态。

### 6.3 角色 prompt profile 接口

- `POST /projects/{project_id}/prompt-profiles/character/generate`
  - 作用: AI 生成角色统一背景提示词草稿
  - 返回: `GenerateJobAck`
- `PATCH /projects/{project_id}/prompt-profiles/character`
  - 作用: 保存角色草稿
  - 请求体: `{ prompt: string }`
  - 返回: 最新 `characterPromptProfile`
- `DELETE /projects/{project_id}/prompt-profiles/character/draft`
  - 作用: 清空角色草稿
  - 返回: 最新 `characterPromptProfile`
- `POST /projects/{project_id}/prompt-profiles/character/confirm`
  - 作用: 把角色草稿应用到 `applied`,然后触发角色资产生成
  - 返回: `GenerateJobAck`

### 6.4 场景 prompt profile 接口

- `POST /projects/{project_id}/prompt-profiles/scene/generate`
- `PATCH /projects/{project_id}/prompt-profiles/scene`
- `DELETE /projects/{project_id}/prompt-profiles/scene/draft`
- `POST /projects/{project_id}/prompt-profiles/scene/confirm`

语义与角色侧完全平行。

### 6.5 为什么不用 `PATCH /projects/{id}` 直接承载

原因如下:

- `generate` 与 `confirm` 都是 workflow action,不是简单字段改写
- `confirm` 包含“写入 applied + 触发下游 job”的复合语义
- 与现有 `parse`、`rollback`、`generate` 等动作式端点保持一致

### 6.6 跳过路径

“跳过并直接生成”不新增后端接口。

具体规则:

- 角色侧跳过:
  - 前端直接调用现有 `/projects/{project_id}/characters/generate`
- 场景侧跳过:
  - 前端直接调用现有 `/projects/{project_id}/scenes/generate`

原因:

- 跳过本质上就是“不启用统一背景提示词,继续现有流程”
- 若额外新增 `skip` 接口,只会复制现有生成逻辑,增加维护面
- 这也能保证“无配置时保持现状”在接口层面是最自然的实现

---

## 7. 异步任务设计

### 7.1 新增 job kind

建议新增 4 个 job kind:

- `gen_character_prompt_profile`
- `gen_scene_prompt_profile`
- `regen_character_assets_batch`
- `regen_scene_assets_batch`

### 7.2 生成草稿任务

`gen_character_prompt_profile` / `gen_scene_prompt_profile` 负责:

1. 读取项目摘要、故事概述、已生成分镜、已存在角色/场景数据
2. 生成适合“保持项目一致性”的统一背景提示词
3. 只写入 `*_prompt_profile_draft`
4. 不触发任何具体角色图/场景图生成

草稿任务必须仍走异步 job,原因:

- LLM 生成存在外部依赖与波动
- 符合“所有远程 AI 调用走 async job”的仓库约束

### 7.3 confirm 后的后续生成

`confirm` 不是新 job,而是同步动作 + 触发下游 job ack:

1. 校验当前阶段是否允许该类资产编辑
2. 校验 draft 非空
3. 将 draft 复制到 applied
4. 根据当前项目数据选择后续链路:

角色侧:

- 若项目还没有角色数据:
  - 触发现有 `/characters/generate`
- 若项目已有角色:
  - 触发 `regen_character_assets_batch`
  - 仅重生成未锁定角色

场景侧:

- 若项目还没有场景数据:
  - 触发现有 `/scenes/generate`
- 若项目已有场景:
  - 触发 `regen_scene_assets_batch`
  - 仅重生成未锁定场景

### 7.4 批量重生成任务边界

批量重生成 job 只负责:

- 遍历当前项目内目标记录
- 跳过 `locked = true` 的记录
- 为每个未锁定记录创建子 job
- 聚合进度

它不负责:

- 重提取角色/场景文本
- 改写角色/场景本身描述
- 推进或回退项目 stage

---

## 8. Prompt 拼装规则

### 8.1 抽象 prompt builder

现有角色图与场景图 prompt 直接写在任务文件里,需要抽成 builder:

- `build_character_asset_prompt(project, character)`
- `build_scene_asset_prompt(project, scene)`

这样可以把“项目级统一背景提示词”拼装逻辑收敛到单点。

### 8.2 角色 prompt 规则

基线仍是当前角色字段:

- 角色名称
- 角色简介
- 角色详述

若 `character_prompt_profile_applied.prompt` 存在,则附加:

```text
项目级统一背景提示词:
{applied.prompt}
```

最终规则:

- 无 applied: 完全保持当前行为
- 有 applied: 在角色自身描述之后追加统一背景提示词

### 8.3 场景 prompt 规则

基线仍是当前场景字段:

- 场景名称
- 场景主题
- 场景简介
- 场景详述

若 `scene_prompt_profile_applied.prompt` 存在,则同样追加项目级统一背景提示词。

### 8.4 不影响镜头渲染

本期不改 [render_shot.py](/Users/macbook/Documents/trae_projects/comic-drama-platform/backend/app/tasks/ai/render_shot.py:1) 的 `prompt_snapshot` 与镜头生成逻辑。

原因:

- 用户当前需求明确针对“角色设定”和“场景设定”
- 先让参考图资产链路获得一致性收益
- 避免把一个中等改动扩成全链路 prompt 重构

---

## 9. 前端设计

### 9.1 位置

配置区放在两个面板顶部:

- 角色: `CharacterAssetsPanel`
- 场景: `SceneAssetsPanel`

位于列表与详情区上方,和现有“新增角色资产 / 新增场景资产”按钮保持同一横向层级。

### 9.2 配置区结构

统一组件建议:

- `PromptProfileCard.vue`

props:

- `kind: "character" | "scene"`
- `profile`
- `busy`
- `locked`
- `primaryActionLabel`

核心 UI 元素:

- 标题: `统一背景提示词`
- 状态标签
- 多行文本输入框
- 次要提示文案
- 按钮组

### 9.3 按钮规则

`未创建`:

- 主按钮: `AI 生成建议`
- 次按钮: `跳过并直接生成角色资产/场景资产`

`草稿中`:

- 主按钮: `确认并生成角色资产/场景资产`
- 次按钮:
  - `重新生成建议`
  - `保存草稿`
  - `清空草稿`

`已应用`:

- 主按钮: `按当前配置重新生成`
- 次按钮:
  - `编辑草稿`
  - `重新生成建议`

`已修改未应用`:

- 主按钮: `确认新配置并生成`
- 次按钮:
  - `恢复到已应用版本`
  - `重新生成建议`
  - `保存草稿`

### 9.4 文案要求

必须明确区分“草稿”和“已生效”:

- `草稿已保存,当前生成仍使用上次确认版本`
- `当前项目尚未启用统一背景提示词`
- `若跳过,系统将直接使用角色/场景自身描述生成参考图`

### 9.5 Store 承载

`workbenchStore.current` 新增:

- `characterPromptProfile`
- `scenePromptProfile`

新增 action:

- `generatePromptProfile(kind)`
- `savePromptProfileDraft(kind, prompt)`
- `clearPromptProfileDraft(kind)`
- `confirmPromptProfileAndGenerate(kind)`
- `skipPromptProfileAndGenerate(kind)`

这些 action 的职责是:

- 调 API
- 注册 job
- 在成功后 `reload()`

不要把草稿状态单独塞进 view-local state;刷新后应从项目详情恢复。

---

## 10. 阶段门禁与状态机约束

### 10.1 不新增 stage

本能力不新增 `project.stage`,原因:

- 它不是生产流程上的新阶段,而是角色/场景资产生成前的可选配置
- 若新增 stage,会破坏现有 `pipeline/transitions.py` 单写入口和 7 段 DAG

### 10.2 沿用现有资产编辑门禁

角色配置区:

- 编辑 / AI 生成 / confirm / skip 直生
- 都要求 `assert_asset_editable(project, "character")`

场景配置区:

- 编辑 / AI 生成 / confirm / skip 直生
- 都要求 `assert_asset_editable(project, "scene")`

因此:

- 角色 prompt profile 仅在 `storyboard_ready` 可操作
- 场景 prompt profile 仅在 `characters_locked` 可操作

### 10.3 锁定记录处理

当 confirm 触发批量重生成时:

- `locked` 记录必须跳过
- 前端结果提示中应说明“已跳过 N 个已锁定角色/场景”

原因:

- 锁定意味着当前资产是后续链路的稳定参考
- 改统一背景提示词不能悄悄破坏锁定资产

---

## 11. 错误处理

### 11.1 错误码

沿用现有错误体系:

- `40001`: draft 为空、prompt 为空白、参数非法
- `40301`: 当前阶段不允许编辑或触发该类生成
- `40401`: 项目不存在
- `40901`: 已有同类 job 在运行
- `42201`: 内容审核/供应商过滤
- `50001`: 未捕获异常

### 11.2 幂等与并发

并发约束:

- 同一项目同一时间只允许一个 `gen_character_prompt_profile`
- 同一项目同一时间只允许一个 `gen_scene_prompt_profile`
- 同一项目同一时间只允许一个“角色资产主生成链路”
- 同一项目同一时间只允许一个“场景资产主生成链路”

推荐做法:

- confirm 前先检查角色/场景生成相关 job 是否处于 `queued/running`
- 若已存在,返回 `40901`

---

## 12. 测试设计

### 12.1 后端

单元测试:

- project detail 正确派生 `characterPromptProfile.status` / `scenePromptProfile.status`
- prompt builder 在有/无 applied 时输出正确
- confirm 对“首次生成”和“批量重生成”分支判断正确
- 批量重生成正确跳过 locked 记录

集成测试:

- `generate draft -> patch draft -> confirm -> trigger generate ack`
- `没有配置时 skip 仍可生成`
- 非法阶段返回 `40301`
- 空 draft confirm 返回 `40001`
- 已有运行中 job 返回 `40901`

### 12.2 前端

组件测试:

- 配置区 4 种状态渲染正确
- 按钮文案、禁用与提示语正确
- `dirty` 状态下提示“当前仍使用已应用版本”

store 测试:

- 生成草稿 job 成功后自动刷新
- confirm 成功后接续角色/场景生成 job
- skip 直接走现有生成接口

---

## 13. 实施建议

建议按以下顺序落地:

1. 数据模型与聚合详情扩展
2. prompt profile schema / service / API
3. AI 生成草稿 job
4. confirm 与批量重生成 job
5. prompt builder 接入角色/场景任务
6. 前端顶部配置区
7. 测试与 smoke 补齐

这样可以保证每一步都有可验证边界,且前后端都能分段联调。

---

## 14. 决策摘要

- 统一背景提示词按项目级维护,分角色与场景两套
- 每套配置都用 `draft/applied` 双版本承载“两阶段生成”
- 无配置时不阻塞流程,完全保持现有行为
- confirm 后才把草稿写入 applied,并触发现有生成链路或批量重生成链路
- 不新增 `project.stage`,仅复用现有资产编辑门禁
- 角色/场景具体任务只读取 `applied`,不读取 `draft`
