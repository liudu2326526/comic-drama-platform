# 漫剧生成平台 — 前端 MVP 设计文档

> **文档版本**:v1.0 · 2026-04-20
> **范围**:MVP 最小闭环前端(工作台 + 项目列表 + 真实后端联调)
> **配套**:
> - 产品文档:`product/comic-drama-product-design.md`
> - 前端 demo(本设计的视觉与交互基线):`product/workbench-demo/`
> - 后端设计:`docs/superpowers/specs/2026-04-20-backend-mvp-design.md`(下文简称"后端 spec")
>
> **约束**:所有页面结构、组件切分、样式基调与 `workbench-demo/` 一致;本文档做的是"把 demo 的只读 UI 变成真实可用的 MVP 产品"的工程化设计,不改视觉风格。

---

## 1. 目标与非目标

### 1.1 目标

- 完全沿用 `workbench-demo/` 的视觉设计和组件划分
- 接入后端 spec §6 定义的 REST API,覆盖 MVP 最小闭环:创建项目 → 解析 → 分镜确认 → 角色锁定 → 场景锁定 → 渲染 → 导出
- 所有异步任务通过 `/api/v1/jobs/{id}` 轮询驱动 UI 进度
- 编辑窗口、回退、主角锁定等后端不变量在 UI 层有一致的禁用/提示反馈
- 镜头版本历史可见、可回退
- 与后端 `ProjectData` 字段一对一,前端不做二次拼装

### 1.2 非目标(本期不做)

- 登录 / 权限 / 多人协作
- 键盘快捷键、拖拽重排(用按钮型 "上移/下移"替代)
- 深色/浅色主题切换(demo 已是深色,MVP 不加 toggle)
- 国际化(全部中文硬编码)
- SSR / SSG(纯 SPA)
- 富文本编辑器、Markdown 渲染、实时协作光标
- 离线模式 / PWA
- 动画过场超出 demo 已有范畴

---

## 2. 技术选型

全部继承 demo,仅新增必要依赖。

| 维度 | 选型 | 备注 |
| --- | --- | --- |
| 语言 | TypeScript 5.7+ `strict: true` | |
| 框架 | Vue 3.5.x `<script setup>` + Composition API | |
| 构建 | Vite 6 | |
| 类型检查 | `vue-tsc` | |
| 路由 | Vue Router 4 (`createWebHistory`) | |
| 状态 | Pinia 2 | 已有 |
| HTTP 客户端 | **Axios 1.x** | 新增;需 interceptor 做统一错误/鉴权/signal 处理 |
| 异步并发 | 浏览器原生 `AbortController` + axios `signal` | |
| 样式 | 原生 CSS(保留 demo 的 global.css 结构) | 不引入 Tailwind / UnoCSS,避免和 demo 视觉分叉 |
| 图标 | 纯文本 + CSS 伪元素(demo 已用) | MVP 不引 icon 库 |
| 消息提示 | 自研极简 `useToast()` composable | 不引 Element Plus / Naive UI |
| 弹窗 | 自研极简 `Modal.vue` 组件 | 用于 rollback 二次确认、删除项目确认 |
| 代码规范 | ESLint + Prettier(沿用 demo 配置,可补) | |
| 包管理 | pnpm(MVP 建议) | |

**关键取舍**:不引 UI 组件库,因为 demo 的视觉是定制深色系 + 大量自定义渐变,UI 库样式会冲突;MVP 组件需求也很有限(列表 / 卡片 / 按钮 / 文本域 / 弹窗 / toast),自研反而轻。

---

## 3. 目录结构

在 `frontend/` 下落地(demo 所在的 `product/workbench-demo/` 作为样式/组件参考源,MVP 后端联调工程迁到 `frontend/`)。

```
frontend/
├── package.json
├── vite.config.ts          # proxy /api → http://127.0.0.1:8000
├── tsconfig.json
├── .env.development        # VITE_API_BASE_URL=/api/v1
├── .env.production
├── index.html
└── src/
    ├── main.ts
    ├── App.vue
    ├── router/
    │   └── index.ts
    ├── api/                        # 接口层(thin,一个业务实体一个文件)
    │   ├── client.ts               # axios 实例 + interceptor
    │   ├── projects.ts
    │   ├── storyboards.ts
    │   ├── characters.ts
    │   ├── scenes.ts
    │   ├── shots.ts
    │   ├── exports.ts
    │   └── jobs.ts
    ├── composables/                # 无状态逻辑复用
    │   ├── useJobPolling.ts        # 统一轮询 /jobs/{id}
    │   ├── useToast.ts
    │   ├── useConfirm.ts
    │   └── useStageGate.ts         # 根据 project.stage 判断操作是否允许
    ├── store/
    │   ├── workbench.ts            # 工作台主 store (已有,需改造接 API)
    │   ├── projects.ts             # 项目列表 store
    │   └── jobs.ts                 # 活跃 jobs 注册表
    ├── types/
    │   ├── api.ts                  # 后端 ENUM + 错误码
    │   └── index.ts                # ProjectData 等前端类型 (已有,需扩)
    ├── utils/
    │   ├── format.ts               # 时长/百分比/时间格式化
    │   ├── ulid.ts                 # 调试用,本地生成临时 id
    │   └── error.ts                # 统一错误展示规则
    ├── views/
    │   ├── ProjectListView.vue     # / 路由
    │   ├── ProjectCreateView.vue   # /projects/new
    │   └── WorkbenchView.vue       # /projects/:id (已有,需改造)
    ├── components/
    │   ├── layout/
    │   │   ├── AppTopbar.vue
    │   │   └── SidebarProjects.vue          # demo 已有,需接 store
    │   ├── common/
    │   │   ├── PanelSection.vue             # demo 已有
    │   │   ├── Modal.vue
    │   │   ├── Toast.vue
    │   │   ├── StatusPill.vue
    │   │   └── ProgressBar.vue
    │   ├── setup/
    │   │   └── ProjectSetupPanel.vue        # demo 已有
    │   ├── storyboard/
    │   │   ├── StoryboardPanel.vue          # demo 已有
    │   │   ├── StoryboardGrid.vue
    │   │   ├── StoryboardDetail.vue
    │   │   └── StoryboardEditModal.vue      # 新增镜头/编辑文案
    │   ├── character/
    │   │   ├── CharacterAssetsPanel.vue     # demo 已有
    │   │   └── CharacterEditModal.vue
    │   ├── scene/
    │   │   ├── SceneAssetsPanel.vue         # demo 已有
    │   │   └── SceneEditModal.vue
    │   ├── generation/
    │   │   ├── GenerationPanel.vue          # demo 已有
    │   │   ├── RenderQueueList.vue
    │   │   ├── RenderVersionHistory.vue     # 版本回退
    │   │   └── RenderRetryBanner.vue
    │   ├── export/
    │   │   └── ExportPanel.vue              # demo 已有
    │   └── workflow/
    │       ├── WorkflowStepNav.vue          # demo 的 chip 条
    │       └── StageRollbackModal.vue
    └── styles/
        ├── global.css              # demo 迁移过来
        ├── variables.css           # 颜色/间距变量,从 demo 提炼
        └── panels.css
```

**约束**:

- `api/` 只负责发请求、返类型化结果,不处理 UI 副作用
- `store/` 只读 `api/` 和自身状态,不直接调 `axios`
- `views/` 只调 `store/` 和 `composables/`,不直接调 `api/`(除非明显的一次性查询)
- `components/` 分业务域目录,避免 demo 现在全部平铺的 8 个 vue 堆在一起

---

## 4. 路由设计

单 SPA,3 条路由对齐产品文档"项目列表 → 新建项目 → 工作台"的三段式,其余子页(分镜/角色/场景/渲染/导出)沿用 demo 的**单页 + 步骤 chip 切换**形态(不做独立路由,避免 MVP 反复跳转)。

| Path | Name | 组件 | 说明 |
| --- | --- | --- | --- |
| `/` | `project-list` | `ProjectListView` | 项目卡片/表格列表,对应 demo 的左侧栏,升级为独立页 |
| `/projects/new` | `project-new` | `ProjectCreateView` | 小说输入 + 触发解析 |
| `/projects/:id` | `workbench` | `WorkbenchView` | 工作台主页(对应 demo `/`) |
| `/projects/:id?step=storyboard\|character\|scene\|render\|export` | 同上 | 通过 query 选中 chip,无需独立路由 | |

**为什么不把 5 个步骤各自做路由**:demo 的设计是所有 panel 都在同一个长页面纵向展示,用户滚动或点 chip 跳锚点;MVP 保持这种结构,可一屏纵览进度。chip 变 active 仅是滚动到对应 `PanelSection` + 更新 `?step=` 参数,不改 DOM 结构。

**路由守卫**:

- `/projects/:id` 进入前调 `workbenchStore.load(id)` 预加载聚合详情;404 或 `ApiError(40401)` → 跳回 `/` 并 toast(`ProjectSummary` 列表职责归 `projectsStore`,**详情职责严格归 `workbenchStore`**,两个 store 不互相调用)
- `/` 进入前调 `projectsStore.fetchList()`(若已加载则跳过)
- `ProjectCreateView` 未填正文直接点"开始拆分分镜"时按钮禁用(本地校验,不走守卫)

---

## 5. 状态管理(Pinia)

拆三个 store,职责互不重叠。

### 5.1 `store/projects.ts` — 项目列表态

```ts
state: {
  list: ProjectSummary[]
  loading: boolean
  keyword: string
  metrics: { label: string; value: string }[]   // sidebar 的三项指标由后端或本地派生
}
actions:
  fetchList()
  createProject(payload) → returns { id, job_id }
  deleteProject(id)
  applyFilter(keyword)   // 纯本地
```

> `ProjectSummary` 是列表视图用的精简体,后端列表接口返回字段更少(`id/name/stage/genre/storyboard_count/character_count/scene_count/updated_at`),避免列表页拉全量 story 文本。

### 5.2 `store/workbench.ts` — 工作台主态(demo 已有,需改造)

```ts
state: {
  current: ProjectData | null       // 来自 GET /projects/:id 聚合
  loading: boolean
  error: string | null

  selectedShotId: string
  selectedCharacterId: string
  selectedSceneId: string
  activeStep: WorkflowStep          // 对齐 ?step= query
  stageGate: StageGateMatrix        // 基于 current.stage 派生
}

actions:
  load(id)                          // 主进入动作
  reload()                          // 操作后刷新
  select{Shot|Character|Scene}(id)
  setStep(step)

  // 写操作封装,全部走 api/,成功后 reload
  editShot(shotId, payload)
  addShot(payload)
  deleteShot(shotId)
  reorderShots(order)
  confirmStoryboards()

  lockCharacter(characterId)
  regenerateCharacter(characterId) → returns jobId
  regenerateScene(sceneId) → returns jobId
  lockScene(sceneId)

  fetchRenderDraft(shotId) → returns { prompt, references }
  confirmRenderShot(shotId, payload) → returns jobId
  renderBatch(force=false) → returns { jobId, subJobIds }
  selectRenderVersion(shotId, renderId)
  lockShot(shotId)

  createExport(config) → returns { exportId, jobId }
  rollbackStage(toStage) → returns invalidatedSummary
```

所有会改服务端状态的 action 成功后都 `reload()` 一次,保证 UI 和后端 `project.stage` 同步。失败走 toast 不 reload。

### 5.3 `store/jobs.ts` — 活跃任务注册表

用于统一生命周期管理和进度展示。

```ts
state: {
  byId: Record<string, JobState>
  activeIds: string[]               // 尚未终态的 job
}

actions:
  register(jobId, meta?)            // 注册并开始轮询
  tick(jobId)                       // 内部轮询一次
  stop(jobId)                       // 卸载
  attachHandler(jobId, onSuccess, onError)   // 终态回调
```

**保证**:

- 同一 `jobId` 多次 register 只启一个轮询
- 组件卸载时 auto stop(由 `useJobPolling` 封装)
- 轮询间隔 `2s`,指数退避最多到 `8s`(后端压力保护),终态后立即停止

---

## 6. API 客户端与轮询

### 6.1 Axios 封装(`api/client.ts`)

```ts
const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,    // /api/v1
  timeout: 15_000
});

client.interceptors.response.use(
  (resp) => {
    if (resp.data?.code === 0) return resp.data.data;
    throw new ApiError(resp.data.code, resp.data.message, resp.data.data);
  },
  (err) => {
    // 网络错误 / 5xx 转成统一 ApiError
    throw ApiError.fromAxios(err);
  }
);
```

统一信封由 interceptor 解包,业务代码直接拿 `data`。`ApiError` 携带后端 `code`,上层用它决定 toast 文案和是否要跳转/回退。

### 6.2 错误码 → 文案映射(`utils/error.ts`)

| code | UI 行为 |
| --- | --- |
| `40001` | toast "参数不合法",若有 `details` 展开在 modal 里 |
| `40301` | toast "当前阶段不允许该操作";附"是否发起回退?"按钮跳 rollback modal |
| `40401` | toast "资源已不存在",自动 `reload()` |
| `40901` | 业务冲突,定制文案(如导出:展示缺失镜头列表) |
| `42901` | toast "AI 限流,请稍后重试",不自动重试 |
| `50001` / `50301` | toast "服务异常,请稍后再试";开发环境打开详细 modal |
| 网络错误 | toast "网络连接失败",按钮提供"重试" |

### 6.3 轮询(`composables/useJobPolling.ts`)

```ts
function useJobPolling(jobId: Ref<string | null>, handlers: {
  onProgress?: (job: JobState) => void,
  onSuccess: (job: JobState) => void,
  onError: (job: JobState) => void,
}): { job: Ref<JobState | null>, cancel: () => void }
```

**语义**:

- `jobId` 变化自动切换轮询目标;置 `null` 停止
- 组件 `onUnmounted` 自动 cancel
- 间隔 2s 起,连续 3 次无变化后退到 4s,再 3 次到 8s(压力保护)
- 返回 `job` 响应式对象,UI 直接渲染 `progress / total / done / error_msg`
- 终态 `succeeded | failed | canceled` 立即停,触发对应 handler

**典型用法**:

```vue
<script setup lang="ts">
const { job } = useJobPolling(jobIdRef, {
  onSuccess: () => { workbench.reload(); toast.success("分镜生成完成"); },
  onError: (j) => toast.error(j.error_msg ?? "生成失败")
});
</script>

<template>
  <ProgressBar v-if="job?.status === 'running'" :value="job.progress" />
</template>
```

---

## 7. 页面与组件

### 7.1 项目列表页 `/`

对应 demo 的 `SidebarProjects.vue` + 顶栏指标,升级为全屏页:

- 顶栏:标题 + "新建项目"按钮
- 搜索/筛选条:关键字(本地)、stage 筛选(请求参数)
- 项目卡片网格(保持 demo 的卡片样式,升级为 grid)
- 每张卡显示:`stage / name / {storyboards}个镜头 · {characters}角色 · {scenes}场景 / updated_at`
- 右上角小菜单:继续编辑 / 复制项目(MVP 可后置) / 删除(带二次确认)

### 7.2 新建项目页 `/projects/new`

- 项目名、genre(下拉:古风权谋 / 学院科幻 / 都市悬疑 / 其他自填)、ratio(固定 9:16)
- 小说正文 textarea,右下角实时字数统计
- 风格/视觉基调/输出目标 三个选填文本
- 底部按钮:**保存草稿** / **开始拆分分镜**
  - "开始拆分分镜":创建项目 → 触发 `/parse` → 跳 `/projects/:id` 并自动轮询 job
- 校验规则:
  - `story` 长度 < 200 字:禁用"开始拆分分镜"并提示
  - `story` > 5000 字:允许但提示"文本较长,解析可能较慢"

### 7.3 工作台 `/projects/:id`(主战场)

整体保留 demo 布局:顶栏 + 左 Sidebar + 主内容(chip 条 + 六段 PanelSection)。

下面对每段 panel 在 MVP 里的"只读 → 可交互"升级点逐一说明。

#### 7.3.1 `ProjectSetupPanel`(新建项目子页)

- 展示 `summary` / `parsedStats` / `setupParams` / `projectOverview`,全部只读
- 若 `stage === draft` 且尚未有 storyboards:**显示"开始拆分分镜"大按钮**,点击触发 `/parse` 并轮询
- 正文 textarea 当前 readonly,MVP 保持 readonly(修改正文要重新走解析,等 M3a 以后再考虑)

#### 7.3.2 `StoryboardPanel`(分镜工作台)

- 卡片网格展示所有 shot(保留 demo 视觉)
- 顶部操作区:
  - `+ 新增镜头`(仅编辑窗口可用)
  - 选中卡片上浮出:`编辑文案` / `上移` / `下移` / `删除` 小按钮
  - 右上角:`确认 N 个镜头`(== `POST /storyboards/confirm`,阶段跃迁)
- **编辑窗口规则** (后端 spec §5.1):
  - `stage ∈ {draft, storyboard_ready}`:全部交互可用
  - 其他阶段:所有写按钮灰化,悬浮提示"当前阶段已锁定,如需修改请 回退阶段"
  - 点"回退阶段"打开 `StageRollbackModal`(§7.3.7)
- 详情区(右侧)展示 `detail` / `tags` / `duration`,同阶段锁定规则
- 分镜文案编辑与后续 render-draft 建议 prompt 需共享同一套“项目级统一视觉设定”语义:
  - 镜头文案应尽量显式写出角色名、场景名、关键道具
  - 避免只写“一个男人 / 一个房间 / 某个地方”这类弱锚点描述
  - 后续进入 `GenerationPanel` 时,render-draft 会在这些镜头信息基础上拼入角色/场景已确认的项目级视觉设定

#### 7.3.3 `CharacterAssetsPanel`

- 角色列表 + 详情(保留 demo)
- 操作按钮:
  - `生成角色资产`(仅 `stage_raw === 'storyboard_ready'`,触发 `/characters/generate` 并轮询)
  - 面板顶部新增“角色统一视觉设定”卡片,用于维护项目级角色 prompt profile 草稿/已应用版本
  - **不提供"手动新增角色"按钮**(MVP 范围外;后端无对应 POST 端点,若 AI 漏识别角色需回退重解析)
  - demo 里的 `新增角色资产` 按钮在 MVP 中隐藏,待后续里程碑补 API 后再开放
- 详情页显示:
  - 参考图(`reference_image_url`);无图时维持 demo 的 `.silhouette` 占位
  - `description` / `meta`
  - 按钮:`编辑描述` / `重新生成参考图`(触发 `/regenerate` job)/ `设为主角 / 锁定`
- 角色统一视觉设定卡片的产品目标不是“多写几句风格词”,而是维护角色参考图共享的项目级视觉圣经,至少覆盖:
  - 世界/时代锚点
  - 画风与材质倾向
  - 角色共性约束(人种、年龄感、服装质感、不可漂移的面部/发型习惯)
  - 跨角色负向约束(禁止风格漂移、禁止额外人物、禁止文字水印)
- 主角锁定后:卡片加 "主角 · 已锁定"角标,所有 meta 编辑禁用(需回退)

#### 7.3.4 `SceneAssetsPanel`

- 与 `CharacterAssetsPanel` 结构对称
- 操作按钮:
  - `生成场景资产`(仅 `stage_raw === 'characters_locked'`,触发 `/scenes/generate` 并轮询)
  - 面板顶部新增“场景统一视觉设定”卡片,用于维护项目级场景 prompt profile 草稿/已应用版本
  - 选中场景后显示:`重新生成参考图` / `锁定`
  - **不提供"手动新增场景"按钮**(理由同角色);demo 里的 `新增场景资产` 按钮在 MVP 中隐藏
- 详情区展示 `theme` 对应的装饰层(demo 的 `theme-palace/academy/harbor`) + 真实参考图
- 场景统一视觉设定卡片的产品目标是维护“场景母版图”的共享空间规则,至少覆盖:
  - 场景的时代/地域/建筑语汇
  - 色板与光影
  - 空间层次与关键结构习惯
  - 跨场景负向约束(禁止时代错置、禁止结构漂移、禁止文字水印)
- 额外:每个场景卡片显示 `usage`(`场景被 X 次 draft/reference 采用`),用于帮助用户理解哪些场景经常被镜头生成引用;**不再提供镜头绑定入口**

#### 7.3.5 `GenerationPanel`(镜头生成页)

demo 最薄弱的 panel,需大幅扩展:

- 顶部:`generationProgress` 文案 + `批量继续生成 / 全量重渲` 按钮(M3c)
- 左列:`RenderQueueList`,每行一个 shot
  - 左侧:`镜头 NN` + title
  - 右侧:`status` 徽标(success / processing / warning) + `版本号 vX`
  - 单行按钮:`生成草稿 / 重新生成` / `查看历史版本`
- 右列:选中 shot 的 `preview-frame + draft editor`
  - 首次进入先调 `/shots/{shot_id}/render-draft`,拿到建议 `prompt + references`
  - 用户可在前端临时编辑 prompt,也可增删建议的角色/场景参考图
  - 点击 `确认生成` 后,才把最终 `prompt + references` 提交给 `/shots/{shot_id}/render`
  - `image_url` 展示当前 render;生成中显示骨架屏 + 轮询 progress
  - `generationNotes` 仅展示当前版本的 prompt / suggestion 摘要,不再作为未提交 draft 的存储来源
- `render-draft` 的建议 prompt 不应是单纯“镜头描述复述”,而应显式继承:
  - 当前 shot 的标题/描述/detail/tags
  - 已确认的角色统一视觉设定
  - 已确认的场景统一视觉设定
  - 被选中的角色/场景参考图
- UI 上应让用户感知到这份建议 prompt 的组成逻辑:
  - 项目视觉规则
  - 镜头目标与站位
  - 角色/场景 references
  - 可手动微调的镜头语言
- 弹出组件:
  - `RenderVersionHistory`:shot 所有 `shot_renders` 的时间轴,缩略图 + `prompt_snapshot` 摘要,点击"切为当前"→ `/renders/{renderId}/select`
  - `RenderRetryBanner`:若 shot `status=failed`,顶部出警示条,分类显示失败原因(对齐后端错误分类)
- 进入导出前置:Panel 显示"锁定全部为最终版"便捷按钮,批量把所有 succeeded → locked
- 阶段门:`stage ∈ {scenes_locked, rendering}` 才能触发渲染;若已到 `ready_for_export` 或 `exported`,需先 rollback

#### 7.3.6 `ExportPanel`

- `exportConfig` / `exportDuration` 展示
- 配置表单(MVP 最小):分辨率、单镜头时长范围、转场(下拉选)、文件名
- `导出 MP4` 按钮:
  - 前置校验:若有 `status ∉ {succeeded, locked}` 的 shot,按钮禁用并列出缺失
  - 校验通过 → POST `/exports` → 轮询 job
  - 409 响应:弹 modal 显示 `pending_shot_ids`,一键跳回 `GenerationPanel` 并高亮
- 任务列表:
  - 每行展示 `name / summary / status / progressLabel`
  - `succeeded` 行显示 `下载 MP4` / `下载封面` 链接(指向 `video_url` / `cover_url`)
  - `failed` 行显示 `重试`(重新 POST `/exports`,复用 config)

#### 7.3.7 `StageRollbackModal`(跨 Panel)

产品文档 §7.5 + 后端 spec §5.1 的 UI 承载。**对应后端端点:`POST /api/v1/projects/{id}/rollback`(后端 spec §6.2 端点表 + §6.3.4 请求示例)**。触发入口:任何阶段门拦截的写操作弹此 modal。

- 展示当前 stage → 目标 stage(默认回到允许修改的最近阶段)
- 列出"将受影响的资产数"(调 `/rollback` 会先通过 `Content-Type: application/json` + dry_run 参数?MVP 简化:不做 dry_run,直接 POST 后展示 `invalidated` 字段)
- 二次确认按钮 `我已了解,执行回退`
- 执行成功 → toast + reload + 关闭 modal

---

## 8. 状态门(Stage Gate)

把后端 spec §5 的编辑窗口规则集中到一个 composable,所有 panel 用同一套判断。

```ts
// composables/useStageGate.ts
// 门控严格与后端状态机(后端 spec §5.1)对齐,不放宽
export function useStageGate() {
  const { current } = storeToRefs(useWorkbenchStore());
  const raw = computed(() => current.value?.stage_raw);

  // 分镜编辑窗口:仅 draft / storyboard_ready
  const canEditStoryboards = computed(() =>
    raw.value === "draft" || raw.value === "storyboard_ready");

  // 触发角色资产生成:仅 storyboard_ready
  const canGenerateCharacters = computed(() => raw.value === "storyboard_ready");

  // 触发场景资产生成:仅 characters_locked
  const canGenerateScenes = computed(() => raw.value === "characters_locked");

  // 渲染镜头:scenes_locked(首次)或 rendering(续跑/失败重试)
  // 明确排除 ready_for_export 与 exported:需 rollback 到 scenes_locked 后再渲染
  const canRender = computed(() =>
    raw.value === "scenes_locked" || raw.value === "rendering");

  // 发起导出:仅 ready_for_export
  // exported 是终态,要再导出需先 rollback 到 ready_for_export
  const canExport = computed(() => raw.value === "ready_for_export");

  // 锁定最终版 shot:rendering | ready_for_export(后期不改素材但可最终化)
  const canLockShot = computed(() =>
    raw.value === "rendering" || raw.value === "ready_for_export");

  // 任意 stage 都可触发回退(目标阶段由 rollback modal 收敛)
  const canRollback = computed(() => raw.value !== null && raw.value !== "draft");

  return {
    canEditStoryboards, canGenerateCharacters, canGenerateScenes,
    canRender, canExport, canLockShot, canRollback
  };
}
```

**gate 与状态机对应表**(两边任何变更都必须同步):

| 操作 | 允许的 `stage_raw` | 不允许的 stage 提示文案 |
| --- | --- | --- |
| 编辑分镜 | `draft`, `storyboard_ready` | "当前阶段已锁定,如需修改请 回退阶段" |
| 生成角色资产 | `storyboard_ready` | "请先确认分镜" / "请先回退" |
| 生成场景资产 | `characters_locked` | "请先锁定主角" / "请先回退" |
| 渲染镜头 | `scenes_locked`, `rendering` | "请先锁定场景" 或 "成片已进入导出阶段,如需重渲请 回退到 `scenes_locked`" |
| 发起导出 | `ready_for_export` | "仍有未完成镜头" 或 "已导出,如需再次导出请 回退到 `ready_for_export`" |
| 锁定镜头最终版 | `rendering`, `ready_for_export` | — |

**注意**:后端 `projects.stage` 是英文 ENUM,`GET /projects/:id` 同时返回展示用中文 `stage`(7 值)和英文 `stage_raw`(7 值)。gate 逻辑只依赖 `stage_raw`,避免中文字面量比较。

---

## 9. 与后端契约对齐

### 9.1 类型一对一

`src/types/index.ts` 的 `ProjectData` 必须与后端 spec §13.1 的映射表完全对齐。MVP 阶段把现有 demo 的类型补齐到:

```ts
export type ProjectStage =
  | "草稿中" | "分镜已生成" | "角色已锁定"
  | "场景已匹配" | "镜头生成中" | "待导出" | "已导出";
export type ProjectStageRaw =
  | "draft" | "storyboard_ready" | "characters_locked"
  | "scenes_locked" | "rendering" | "ready_for_export" | "exported";

export interface ProjectData {
  id: string; name: string;
  stage: ProjectStage;
  stage_raw: ProjectStageRaw;       // 新增
  genre: string; ratio: string; suggestedShots: string;
  story: string; summary: string;
  parsedStats: string[]; setupParams: string[]; projectOverview: string;
  storyboards: StoryboardShot[];
  characters: CharacterAsset[];
  scenes: SceneAsset[];
  generationProgress: string;
  generationNotes: { input: string; suggestion: string };
  generationQueue: RenderQueueItem[];
  exportConfig: string[];
  exportDuration: string;
  exportTasks: ExportTask[];
}
```

其他(StoryboardShot / CharacterAsset / SceneAsset / RenderQueueItem / ExportTask)对应后端 spec §13.1 保持同步。其中 `RenderQueueItem` 已从 demo 时代的 shot 列表升级为 **job-based queue item**:前端基于 `storyboards + generationQueue` 组合出镜头视图,`characters.role` / `scenes.usage` / `exportTasks.progressLabel` 由后端格式化好直出。

### 9.2 展示值 vs 原始值

| 场景 | 展示值 | 原始值 |
| --- | --- | --- |
| 项目 stage | `stage`(中文 7 值) | `stage_raw`(英文 ENUM)|
| shot duration | `duration` 字符串 `"3.5 秒"` | 无需(MVP 不改 shot 时长) |
| 渲染状态 | `RenderQueueItem.status`(success/processing/warning) | 无 |
| export 状态 | `ExportTask.status` + `progressLabel` | 无 |

**原则**:展示值由后端拼,前端不做格式化;原始值只在需要做阶段门判断或写回后端时用。

### 9.3 API 调用收口

`api/` 下每个文件导出的函数签名必须和后端 spec §6.2 端点 1:1。例如:

```ts
// api/shots.ts
export const shotsApi = {
  renderBatch: (projectId: string, body: { shot_ids: string[] | null; force_regenerate: boolean }) =>
    client.post<void, { job_id: string; sub_job_ids: string[] }>(`/projects/${projectId}/shots/render`, body),
  fetchRenderDraft: (projectId: string, shotId: string) =>
    client.post<void, { shot_id: string; prompt: string; references: RenderDraftReference[] }>(
      `/projects/${projectId}/shots/${shotId}/render-draft`
    ),
  renderOne: (projectId: string, shotId: string, body: { prompt: string; references: RenderDraftReference[] }) =>
    client.post<typeof body, { job_id: string }>(`/projects/${projectId}/shots/${shotId}/render`, body),
  listRenders: (projectId: string, shotId: string) =>
    client.get<void, RenderVersion[]>(`/projects/${projectId}/shots/${shotId}/renders`),
  selectRender: (projectId: string, shotId: string, renderId: string) =>
    client.post<void, void>(`/projects/${projectId}/shots/${shotId}/renders/${renderId}/select`),
  lock: (projectId: string, shotId: string) =>
    client.post<void, void>(`/projects/${projectId}/shots/${shotId}/lock`)
};
```

---

## 10. 交互状态(Loading / Error / Empty)

每个 Panel 必须显式处理这三态,不允许"默默渲染空"。

| 场景 | 表现 |
| --- | --- |
| 首次进入 `/projects/:id` | 整页骨架屏(保留 demo 布局,卡片/文本块都是占位条) |
| Panel 内部刷新 | 该 Panel 顶部显示 `loading` 细条(`ProgressBar` indeterminate 模式) |
| 后端 500 | 整页报错卡片 + `重试`按钮 |
| `stage === draft` 且无 storyboards | `StoryboardPanel` 显示 "尚未生成分镜 · 请先返回上方'开始拆分分镜'" |
| 无角色/场景/镜头 | 各 Panel 空态:图标 + 引导文案 + 对应生成按钮 |
| 生成 job 运行中 | Panel 对应区块 disabled + 顶部 `ProgressBar` 显示 `progress%` |
| 生成 job 失败 | Panel 顶部红色 banner,文字:失败类别 + 错误摘要 + `重试` 按钮 |

---

## 11. 消息系统

### 11.1 `useToast`

```ts
const toast = useToast();
toast.success("主角已锁定");
toast.error("操作失败", { detail: err.message, persist: false });
toast.info("正在触发重新生成...");
toast.warning("当前阶段已锁定,修改需先回退", { action: { label: "回退", onClick: openRollback } });
```

- 右上角纵向堆叠,最多 5 条,3 秒自动消失(error 5s)
- 支持一个 action 按钮(用于跳转到 rollback / retry 等)

### 11.2 `useConfirm`

```ts
const ok = await confirm({
  title: "删除项目?",
  body: "所有镜头、资产和已导出视频将一并删除,不可恢复。",
  confirmText: "确认删除",
  danger: true
});
```

---

## 12. 样式与主题

- 全盘继承 `product/workbench-demo/src/styles/global.css`,迁移到 `frontend/src/styles/global.css`
- 提炼颜色/间距变量到 `variables.css`:
  ```css
  :root {
    --bg-gradient: ...;
    --panel-bg: ...;
    --accent: ...;
    --accent-dim: ...;
    --danger: #f05a5a;
    --success: #5cd6a9;
    --warning: #f1a34b;
    --radius-lg: 18px;
    --radius-md: 12px;
    --space-*: ...;
  }
  ```
- Panel、status pill、chip、tag 等现有 class 保留原名,新组件沿用(例如 `Modal.vue` 内部用 `panel-head / panel-kicker`)
- 不引入 CSS-in-JS;每个 Vue 组件需要局部样式用 `<style scoped>`,但**避免** override demo 的全局 class

---

## 13. 性能与资源

- 路由懒加载:`ProjectCreateView`、`WorkbenchView` 用 `() => import()` 拆 chunk
- 图片懒加载:参考图 / render 结果图统一 `<img loading="lazy">`
- 轮询在页面 `visibilitychange` 为 hidden 时暂停,visible 恢复(减少后台拉取)
- `parseTasks` 这类大数据 MVP 不做虚拟滚动;shot 列表超过 30 条再考虑(后端 spec 未明确限制,暂不优化)

---

## 14. 构建与部署

### 14.1 环境变量

```
# .env.development
VITE_API_BASE_URL=/api/v1

# .env.production
VITE_API_BASE_URL=/api/v1
VITE_STATIC_BASE_URL=http://comic.internal/static
```

`VITE_STATIC_BASE_URL` 仅在展示 `reference_image_url` / `video_url` 时拼完整路径(若后端已返回完整 URL 则不用)。

### 14.2 开发代理

```ts
// vite.config.ts
server: {
  proxy: {
    "/api": "http://127.0.0.1:8000",
    "/static": "http://127.0.0.1:8000"
  }
}
```

### 14.3 生产部署

- `pnpm build` 产出 `dist/`
- Nginx 同域挂载:`/` → `dist/`,`/api/` → FastAPI,`/static/` → 后端约定的 `/data/assets/`
- 开启 Brotli + 长缓存 for `assets/` 指纹化资源

---

## 15. 里程碑(对齐后端 M1-M5)

| M | 前端交付 |
| --- | --- |
| M1 | 工程脚手架:Vite + TS + Vue Router + Pinia + axios;迁移 demo 的静态样式和组件;联调项目 CRUD 和 `/rollback`;引入 `useJobPolling` 空壳 |
| M2 | 接入 mock 后端的 `/parse` + `/storyboards/*`;`ProjectSetupPanel` 和 `StoryboardPanel` 真实可交互;状态门初版 `useStageGate` 上线 |
| M3a | `CharacterAssetsPanel` / `SceneAssetsPanel` 写操作打通(编辑/生成/锁定/重生成),版本历史入口上线 |
| M3b | `GenerationPanel` + `RenderVersionHistory`:单镜头 `render-draft → confirm render`、切换版本、失败重试 |
| M3c | 批量渲染 UI + job-based queue 聚合展示 + worker crash 后前端对 running job 的恢复提示 |
| M4 | `ExportPanel` 完整链路 + 下载 + 完整性校验 + 409 缺失列表跳转 |
| M5 | 错误码全量文案覆盖、toast / confirm / modal 三件套打磨、空态/错误态/骨架屏全量上线、生产 build 和 Nginx 联调通过 |

---

## 16. 风险与开放问题

- **~~`stage_raw` 字段~~**:已同步到后端 spec §13.1 / §13.2(7 值中文 + 7 值英文双字段),不再是开放项
- **参考图加载延迟**:火山图像生成返回的 `image_url` 如果不是稳定 CDN,首次打开 workbench 时批量懒加载可能抖。MVP 接真实后端时观察,必要时前端加一层 `loading=eager` + skeleton
- **轮询风暴**:同一项目同时跑 14+ 个 `render_shot` 子 job,如果每个都独立轮询会扎后端。**对策**:优先依赖后端聚合返回的 `generationQueue`(job-based) 恢复和展示子状态;批量渲染时可重点轮询 `render_batch` 父 job 的总进度,但单镜头/子镜头的失败原因与进度不强依赖父 job `result`
- **离线编辑回写**:MVP 无本地草稿缓存,若浏览器崩掉,用户在 `ProjectCreateView` 的未提交输入会丢。MVP 不做 localStorage 缓存,留待后期
- **版本历史磁盘占用**:UI 展示历史 render 图片,但后端 spec 说明不自动清理;前端 MVP 不主动暴露"清理非当前版本"的按钮(对应后端 `/admin/projects/:id/vacuum`),留到运维/后台

---

## 17. 一句话总结

本设计把 `workbench-demo/` 的静态原型**原样保留视觉与信息架构**,通过一层 `api/` + `store/` + `composables/` 接入后端 REST 与轮询,并在所有写路径上强制走 `useStageGate` 判定 + `StageRollbackModal` 兜底,使前端在不改 UX 的前提下,能忠实地表达后端 spec 的编辑窗口、版本回退、导出快照三条核心不变量。
