# 漫剧生成平台 — 项目级统一视觉设定设计文档

> **文档版本**: v1.0 · 2026-04-23
> **范围**: 角色设定 / 场景设定 / 分镜工作台中的项目级统一视觉设定
> **配套**:
> - 后端设计: `docs/superpowers/specs/2026-04-20-backend-mvp-design.md`
> - 前端设计: `docs/superpowers/specs/2026-04-20-frontend-mvp-design.md`
> - 当前工作台界面: `frontend/src/components/character/CharacterAssetsPanel.vue`、`frontend/src/components/scene/SceneAssetsPanel.vue`

---

## 1. 目标与非目标

### 1.1 目标

- 为每个项目新增“统一视觉设定”能力,作为项目级视觉圣经,优先服务于:
  - 角色参考图生成
  - 场景母版图生成
  - 分镜工作台 render-draft 建议 prompt
- 首版仍以两份项目级配置承载该能力:
  - 角色视觉设定 prompt profile
  - 场景视觉设定 prompt profile
- 配置采用两阶段工作流:
  - 先生成或编辑配置草稿
  - 用户确认后,再触发具体角色图或场景图生成
- 已确认配置在后续每个角色/场景出图时自动拼入 prompt,并在分镜工作台生成 render-draft 时作为统一视觉约束输入,提升同项目内视觉一致性
- 若用户从未创建配置,系统保持现有行为,不阻塞流程也不附加额外 prompt
- 保持现有异步任务模型: HTTP 只返回 ack,实际生成仍由 Celery job 执行

### 1.2 非目标

- 不新增新的 `project.stage`
- 不强制用户必须创建或确认统一视觉设定后才能继续流程
- 不在首版引入复杂 prompt 结构编辑器(如负向提示词、多段标签、权重参数)
- 不在首版自动重生成所有已生成资产;只有用户在“确认并生成”时才触发后续生成
- 不新增第三套独立的 `storyboard prompt profile` 资源
- 不直接改 provider 执行阶段 `render_shot.py` 的协议;本期只要求 `render-draft` 继承项目级视觉设定,最终 `render_shot` 继续消费用户确认后的 `prompt_snapshot`

---

## 2. 产品定义

### 2.1 核心概念

项目级统一视觉设定是项目层面的“视觉圣经”,不是单个角色/场景记录自身的描述字段,也不是一句泛化的“电影感/高级感”修饰词。

它应该稳定约束以下维度:

- 世界观与时代背景
- 画风与材质倾向
- 色板与光影系统
- 镜头语言与构图习惯
- 角色共性约束
- 场景共性约束
- 跨资产负向约束

本期一个项目有两套独立配置,外加一个复用入口:

- `character prompt profile`: 用于角色参考图生成
- `scene prompt profile`: 用于场景母版图生成
- `render-draft`: 不单独存 profile,而是在生成镜头建议 prompt 时复用前两者的已确认版本

两套配置各自维护,但在镜头层共同组成统一项目视觉约束。

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

统一视觉设定是可选能力,不是强制门槛。

- 用户未创建配置:
  - 角色生成沿用现有角色 prompt
  - 场景生成沿用现有场景 prompt
- 用户创建了草稿但未确认:
  - 后续生成仍不使用草稿
- 用户确认后:
  - 该类型后续生成都自动拼入对应 `applied.prompt`
  - 分镜工作台生成 render-draft 时可读取已确认的角色/场景视觉设定,一起形成镜头建议 prompt

---

## 3. 用户流程

### 3.1 角色统一视觉设定

入口位于角色设定面板顶部,即当前“新增角色资产”按钮左侧的大块预留区。

用户路径:

1. 用户进入角色设定页(`stage_raw = storyboard_ready`)
2. 顶部看到“统一视觉设定”配置区
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

### 3.2 场景统一视觉设定

入口位于场景设定面板顶部,即当前“新增场景资产”按钮左侧的大块预留区。

用户路径与角色侧一致,但阶段与触发链路切换为场景侧:

1. 用户进入场景设定页(`stage_raw = characters_locked`)
2. 用户生成或编辑场景统一视觉设定草稿
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
  - 写入与读取都应经过统一校验,避免历史脏数据把空串带回前端
- `source: "ai" | "manual"`
  - 用于前端提示“由 AI 生成”或“手动编辑”
  - 不参与生成逻辑

虽然首版仍落为单个 `prompt` 字段,但其语义不应是“多写几个形容词”,而应是项目级视觉规则摘要。推荐包含:

- `world_era`: 世界/时代锚点
- `visual_style`: 画风锚点
- `palette_lighting`: 色板与光影
- `lens_language`: 镜头与构图习惯
- `character_rules`: 角色共性约束
- `scene_rules`: 场景共性约束
- `negative_rules`: 跨资产禁止项

这些内容首版仍通过一段自然语言写入 `prompt`,后续再视需要拆成结构化字段。

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

返回契约补充:

- 当 `status = "empty"` 时: `draft = null`, `applied = null`
- 当 `status = "draft_only"` 时: `draft != null`, `applied = null`
- 当 `status = "applied"` 且此前从未手改草稿时: 允许返回 `draft = applied`
- 当前方案推荐在 `draft == applied` 时保留两者都返回,由前端严格以 `status` 驱动按钮矩阵,不要用 `draft != null` 误判为“草稿中”
- 若后续要简化前端判断,可在二期把 `status = "applied"` 时的 `draft` 置空,但首版需先把契约钉死

### 6.3 角色 prompt profile 接口

- `POST /projects/{project_id}/prompt-profiles/character/generate`
  - 作用: AI 生成角色统一视觉设定草稿
  - 并发要求: 若已有 `gen_character_prompt_profile` 或角色资产主生成链路在 `queued/running`,返回 `40901`
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
  - 并发要求: 若已有角色资产主生成链路在 `queued/running`,返回 `40901`
  - 返回: `GenerateJobAck`

### 6.4 场景 prompt profile 接口

- `POST /projects/{project_id}/prompt-profiles/scene/generate`
- `PATCH /projects/{project_id}/prompt-profiles/scene`
- `DELETE /projects/{project_id}/prompt-profiles/scene/draft`
- `POST /projects/{project_id}/prompt-profiles/scene/confirm`

语义与角色侧完全平行,并同样要求在 `generate / confirm` 时做 `40901` 并发守门。

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

- 跳过本质上就是“不启用统一视觉设定,继续现有流程”
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
2. 生成适合“保持项目一致性”的统一视觉设定
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
- `build_storyboard_render_draft_prompt(project, shot, references)`

这样可以把“项目级统一视觉设定”拼装逻辑收敛到单点,并确保角色、场景、镜头三层共享同一套项目视觉锚点。

### 8.2 角色 prompt 规则

角色 prompt 的目标不是“生成一张好看的人像”,而是“生成后续全链路可复用的角色标准参考图”。

基线字段仍来自当前角色记录:

- 角色名称
- 角色简介
- 角色详述

若 `character_prompt_profile_applied.prompt` 存在,则附加:

```text
项目级统一视觉设定:
{applied.prompt}
```

最终规则:

- 角色 prompt 先声明“项目级统一视觉设定”,再声明角色自身信息
- 明确用途为“角色设定参考图/角色标准图”,而不是普通剧情插图
- 角色自身描述必须突出稳定辨识点:
  - 面部与发型
  - 年龄感与体态
  - 服装层次与关键配饰
  - 不可漂移的标志性细节
- 明确构图要求:
  - 单人
  - 全身或七分身
  - 纯净/弱化背景
  - 便于后续镜头引用
- 必须附加负向约束:
  - 禁止多人
  - 禁止复杂背景抢主体
  - 禁止五官漂移
  - 禁止额外道具
  - 禁止文字/水印

### 8.3 场景 prompt 规则

场景 prompt 的目标不是“一张氛围图”,而是“可被多个镜头复用的场景母版图”。

基线字段仍来自当前场景记录:

- 场景名称
- 场景主题
- 场景简介
- 场景详述

若 `scene_prompt_profile_applied.prompt` 存在,则同样追加项目级统一视觉设定。

最终规则:

- 场景 prompt 先声明“项目级统一视觉设定”,再声明场景自身信息
- 明确用途为“场景设定参考图/场景母版图”
- 场景自身描述必须突出空间锚点:
  - 关键结构与必出现物件
  - 前景/中景/后景层次
  - 材质、时间段、天气与氛围
- 默认弱化人物或不出现人物,避免角色信息污染场景母版
- 必须附加负向约束:
  - 禁止结构混乱
  - 禁止无关人物抢画面
  - 禁止时代错置
  - 禁止风格跳变
  - 禁止文字/水印

### 8.4 分镜工作台 prompt 规则

本期不新增独立的 storyboard prompt profile 资源,但 `render-draft` 需要继承项目级统一视觉设定。

规则:

- `render-draft` 的建议 prompt 由以下信息共同构成:
  - `character_prompt_profile_applied.prompt`
  - `scene_prompt_profile_applied.prompt`
  - shot 自身标题/描述/detail/tags
  - 已选择或推荐的角色/场景 references
- 镜头 prompt 结构必须比当前摘要式文案更工程化,至少包含:
  - 镜头目标
  - 出场资产(角色名/场景名/道具名)
  - 站位与景别
  - 动作与情绪
  - 单一主运镜
  - 连续性约束
  - 负向约束
- `render_shot.py` 继续消费用户最终确认后的 `prompt_snapshot`,不直接参与 profile 拼装

这样可以让分镜工作台与角色/场景资产共用同一套视觉圣经,同时避免把本期范围扩成第三套 profile 资源与全链路 provider 协议重构。

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

- 标题: `统一视觉设定`
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
- `当前项目尚未启用统一视觉设定`
- `若跳过,系统将直接使用角色/场景自身描述生成参考图`

### 9.5 Store 承载

`workbenchStore.current` 新增:

- `characterPromptProfile`
- `scenePromptProfile`

新增 action:

- `generatePromptProfile(kind)`
- `savePromptProfileDraft(kind, prompt)`
- `clearPromptProfileDraft(kind)`
- `restoreAppliedPromptProfileDraft(kind)`
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
- 改统一视觉设定不能悄悄破坏锁定资产

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

- `generate` 前先检查:
  - 同类 profile 生成 job 是否处于 `queued/running`
  - 对应角色/场景资产主生成链路是否处于 `queued/running`
- `confirm` 前先检查:
  - 对应角色/场景资产主生成链路是否处于 `queued/running`
- 建议收敛为统一 helper 或 service 入口,避免 `generate` / `confirm` 各自漏掉一半并发守门
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

- 统一视觉设定按项目级维护,分角色与场景两套
- 每套配置都用 `draft/applied` 双版本承载“两阶段生成”
- 无配置时不阻塞流程,完全保持现有行为
- confirm 后才把草稿写入 applied,并触发现有生成链路或批量重生成链路
- 不新增 `project.stage`,仅复用现有资产编辑门禁
- 角色/场景具体任务只读取 `applied`,不读取 `draft`
