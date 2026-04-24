# 项目级角色风格参考图 — 产品与工程设计

> 文档版本:v1.0 · 2026-04-24  
> 范围:角色设定页增强  
> 关联模块:`CharacterAssetsPanel`、`PromptProfileCard`、角色资产生成、项目聚合接口、OBS 资产存储  
> 设计原则:角色风格参考图是项目级风格母版,不绑定具体剧情角色;生成必须异步;图片必须落入项目资产域并可刷新恢复。

---

## 1. 背景

当前角色生成链路已经有“角色统一视觉设定”文本,用于约束画风、脸型气质、服装材质和镜头语言。但仅靠文本约束仍容易出现以下问题:

- 不同角色的画风、身体比例、服装质感不稳定。
- 后续重生成时,人物正面全身比例可能漂移。
- 用户缺少一个可视化的“项目角色风格锚点”来确认统一设定是否符合预期。

因此新增一张项目级“统一角色形象参考图”。它是一张白底、正面、全身、单人示范图,用于固定全项目人物风格形象。它不代表某个具体角色身份,只作为后续角色参考图生成的风格母版。

---

## 2. 目标与非目标

### 2.1 目标

- 在“角色统一视觉设定”旁边展示一张项目级角色风格参考图。
- 参考图要求:单人、正面、全身、白色背景、无文字水印、无复杂道具。
- 支持生成、重生成、失败重试、生成中进度展示。
- 生成结果保存到项目级数据,刷新页面后仍可展示。
- 后续生成具体角色参考图时,自动把该图作为风格参考输入,但仍以具体角色描述为主。
- 不阻塞 HTTP 请求,所有远程 AI / 出图 / 上传动作必须走异步 job。

### 2.2 非目标

- 不做多张风格图版本管理;MVP 只保存当前生效图。
- 不做跨项目风格母版复用。
- 不做用户本地图片上传作为母版;如后续支持上传,必须先走资产存储和内容安全校验。
- 不把风格参考图注册到火山人像库;它是风格母版,不是具体人物身份。
- 不改变项目阶段流转,仍沿用现有角色设定阶段权限。

---

## 3. 产品体验

### 3.1 页面布局

角色设定页顶部从单卡片变为双栏布局:

```text
角色设定
├── 左侧:角色统一视觉设定
│   ├── AI 生成建议
│   ├── 设定文本编辑
│   ├── 保存草稿
│   └── 确认并生成角色
└── 右侧:统一角色形象参考图
    ├── 白底正面全身预览
    ├── 状态:未生成 / 生成中 / 已生成 / 失败
    └── 操作:生成参考图 / 重新生成 / 重试
```

桌面端:

- 左侧沿用现有 `PromptProfileCard`。
- 右侧新增 `CharacterStyleReferenceCard`。
- 两栏高度不强行相等,右侧卡片以预览图为主,保持清爽。

窄屏端:

- 上下排列。
- 先显示“角色统一视觉设定”,再显示“统一角色形象参考图”。

### 3.2 状态设计

| 状态 | UI 表现 | 可用操作 |
| --- | --- | --- |
| 未生成 | 白底占位 + 人物轮廓 | 生成参考图 |
| 生成中 | 进度条 + 文案“正在生成统一角色形象参考图” | 禁用重复提交 |
| 已生成 | 展示图片 + 生成时间 | 重新生成 |
| 失败 | 错误文案 + 弱提示 | 重试 |
| 阶段锁定 | 操作按钮禁用 | 提示回退阶段 |

### 3.3 文案

卡片标题:

```text
统一角色形象参考图
```

说明文案:

```text
用于统一后续角色参考图的人物比例、画风、服装质感和白底全身形象,不绑定具体剧情角色。
```

按钮:

- 未生成:`生成参考图`
- 生成中:`生成中...`
- 已生成:`重新生成`
- 失败:`重试`

---

## 4. 数据设计

MVP 使用 `projects` 表保存当前生效图,避免新增版本管理复杂度。

### 4.1 Project 新增字段

```text
character_style_reference_image_url: string | null
character_style_reference_prompt: JSON | null
character_style_reference_status: string | null
character_style_reference_error: string | null
```

字段含义:

- `character_style_reference_image_url`: OBS object key 或已规范化的项目资产 key,聚合接口输出时转为可访问 URL。
- `character_style_reference_prompt`: 生成时的 prompt snapshot,用于排查和复现。
- `character_style_reference_status`: `empty | running | succeeded | failed`。
- `character_style_reference_error`: 最近一次失败原因。

### 4.2 聚合响应

`ProjectData` 增加:

```ts
characterStyleReference: {
  imageUrl: string | null;
  prompt: string | null;
  status: "empty" | "running" | "succeeded" | "failed";
  error: string | null;
}
```

如果后端没有字段或老项目为空,前端按 `empty` 处理。

---

## 5. API 设计

### 5.1 生成 / 重生成

```http
POST /api/v1/projects/{project_id}/character-style-reference/generate
```

返回:

```json
{
  "job_id": "01..."
}
```

约束:

- 只允许在 `storyboard_ready` 阶段触发,与角色统一视觉设定编辑权限一致。
- 若已有同类 running job,返回 409。
- 远程 AI 出图、OBS 上传必须在 Celery 任务中执行。

### 5.2 查询

不新增单独查询接口,通过现有项目聚合接口返回 `characterStyleReference`。

### 5.3 Job kind

新增:

```text
gen_character_style_reference
```

进度建议:

- 10: 创建任务
- 30: 组装提示词
- 70: 调用出图模型
- 90: 上传 OBS / 写回项目
- 100: 完成

---

## 6. 生成 Prompt

### 6.1 风格母版生成 Prompt

```text
生成一张项目级角色风格参考图,用于统一后续所有角色参考图的视觉风格。

画面内容:
单人,正面站立,全身像,人物完整入画,头顶到脚底可见,姿态端正自然,双臂自然下垂或轻微收拢,不做夸张动作。

背景要求:
纯白背景,干净无场景,无道具,无文字,无水印,无边框。

人物风格:
根据以下项目级角色统一视觉设定生成一个中性示范人物,不绑定具体剧情角色身份,不出现明确姓名标识。
保持统一的脸型比例、五官风格、发型质感、服装层次、材质表现、色彩体系、光影方式和整体画风。

项目级角色统一视觉设定:
{{character_prompt_profile}}

构图要求:
正面全身,角色居中,竖图构图,身体比例稳定,服装轮廓清晰,面部清楚,手部自然,脚部完整。

禁止项:
禁止多人,禁止复杂背景,禁止半身像,禁止侧脸,禁止背影,禁止过度动态姿势,禁止遮挡身体,禁止文字水印,禁止道具抢画面,禁止背景色非白色,禁止风格漂移。
```

### 6.2 具体角色生成 Prompt 追加规则

如果项目存在 `character_style_reference_image_url`,具体角色参考图生成时追加:

```text
项目级角色风格参考图使用规则:
- 参考该图的人物画风、身体比例、服装材质、白底全身构图和渲染质感。
- 只继承风格与形象规范,不要继承示范人物的具体身份、姓名或剧情关系。
- 当前输出必须严格根据本角色的名称、简介和详述生成。
- 背景仍保持简洁,不要添加复杂场景。
```

同时在调用多模态图像生成时,把该图作为第一张 reference image;具体角色已有其它引用时排在其后。

---

## 7. 工程改造

### 7.1 Backend

新增/修改:

- `Project` ORM 增加字段和 Alembic migration。
- `ProjectRead` / 聚合 schema 增加 `characterStyleReference`。
- 新增 `app/api/character_style_reference.py`。
- 新增 service: `CharacterStyleReferenceService`。
- 新增 Celery task: `ai.gen_character_style_reference`。
- `build_character_asset_prompt` 增加风格母版引用说明。
- 角色出图任务在存在风格母版时传入 reference image。

阶段与权限:

- 复用 `canEditCharacters` 对应的后端阶段约束。
- 不直接修改 `project.stage`。
- job 状态仍通过 `update_job_progress` 写入。

### 7.2 Frontend

新增/修改:

- 新增组件 `CharacterStyleReferenceCard.vue`。
- `CharacterAssetsPanel.vue` 顶部新增 `character-profile-layout` 双栏。
- `workbench` store 增加:
  - `activeCharacterStyleReferenceJobId`
  - `generateCharacterStyleReference`
  - `markCharacterStyleReferenceSucceeded`
  - `markCharacterStyleReferenceFailed`
- `useJobPolling` 接入 `gen_character_style_reference`。
- `ProjectData` 类型增加 `characterStyleReference`。

布局建议:

```css
.character-profile-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.8fr);
  gap: 18px;
  align-items: start;
}
```

---

## 8. 错误处理

- 没有角色统一视觉设定时仍可生成,但 prompt 中使用项目类型、摘要和默认风格约束。
- 出图失败:写入 `character_style_reference_status=failed` 和错误信息,前端展示重试。
- OBS 上传失败:任务失败,不覆盖上一张成功图。
- 重生成成功前,前端仍展示上一张成功图,并叠加“新图生成中”状态。
- 阶段不允许时:返回 40301,前端给出回退阶段提示。

---

## 9. 验收标准

- 角色设定顶部能看到“角色统一视觉设定”和“统一角色形象参考图”并排展示。
- 未生成时有明确占位和“生成参考图”按钮。
- 点击生成后返回 job,页面展示进度,刷新后能重新接管 running job。
- 生成成功后展示白底正面全身人物图。
- 刷新页面后图片仍存在。
- 重新生成失败不会清掉上一张成功图。
- 后续生成具体角色参考图时,角色图能继承项目级风格母版的人物比例、画风和服装质感。
- 具体角色图不会被误生成为风格母版中的示范人物身份。
- 所有远程 AI 调用均在 Celery job 中执行,HTTP 请求不阻塞等待出图。

---

## 10. 实施顺序

1. 后端 migration + schema + 聚合响应。
2. 新增生成 API 和 Celery task。
3. 接入 OBS 保存和 job 进度。
4. 修改角色资产生成 prompt/reference image 输入。
5. 前端新增 `CharacterStyleReferenceCard` 和 store job 追踪。
6. 页面联调:生成、刷新恢复、失败重试、重生成不覆盖旧图。
7. 增加单元测试和一条前端 smoke 验证。
