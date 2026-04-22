# Frontend M1: 前端工程脚手架 + 项目 CRUD/Rollback 联调 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `frontend/` 下落地可运行的 Vue 3 + Vite + TS + Router + Pinia + Axios 工程骨架;把 `product/workbench-demo/` 的静态视觉与组件结构**原样迁移**到 `frontend/`;打通后端 M1 的 `projects` CRUD 与 `/rollback` 两类端点(含中英双字段 `stage` / `stage_raw`);引入 `useJobPolling` / `useStageGate` 骨架(不接真实 job,为 M2 留接口)。

**Architecture:** 严格遵循 `docs/superpowers/specs/2026-04-20-frontend-mvp-design.md`(下文简称"前端 spec")§3 目录分层:`api/` 做纯请求、`store/` 只读 `api/` 和自身状态、`views/` 只调 `store/` 和 `composables/`、`components/` 按业务域分组。样式与交互**不做任何视觉再设计**,继承 demo 的深色调。

**Tech Stack:** Node 20+ / pnpm 9+ / Vue 3.5 `<script setup>` / TypeScript 5.7 `strict` / Vite 6 / Vue Router 4 `createWebHistory` / Pinia 2 / Axios 1.x / 原生 CSS(**不引 UI 组件库**,沿用 demo 定制深色风格)/ Vitest + @vue/test-utils(仅用于纯逻辑/composable 单测)。

**References:**
- 前端设计文档:`docs/superpowers/specs/2026-04-20-frontend-mvp-design.md`
- 后端设计文档:`docs/superpowers/specs/2026-04-20-backend-mvp-design.md` §6(端点)/§13(字段映射)
- Backend M1 plan:`docs/superpowers/plans/2026-04-20-backend-m1-skeleton.md`(M1 已交付 `POST/GET/PATCH/DELETE /api/v1/projects` + `POST /api/v1/projects/{id}/rollback`)
- 视觉与组件参考源:`product/workbench-demo/`(M1 只迁结构,不改视觉)

---

## M1 范围与非范围(对齐前端 spec §15)

### 本里程碑交付

- 全新 `frontend/` 工程可 `pnpm dev` 启动,`pnpm build` 过 `vue-tsc + vite build`
- Axios 实例 + 统一响应信封拆包 + `ApiError` + 错误码 → toast 映射骨架
- Pinia 三 store(`projects` / `workbench` / `jobs`)初版,职责不重叠
- `ProjectListView` 可列出后端真实项目;`ProjectCreateView` 可创建项目(M1 暂不触发 `/parse`);`WorkbenchView` 可加载 `GET /projects/:id` 并驱动 demo 各 panel 只读展示
- `StageRollbackModal` 可触发 `POST /rollback`;失败走统一 toast
- `useJobPolling`(空壳,按真实接口签名实现但 M1 不挂真实 job;单测覆盖退避/终态逻辑)
- `useStageGate` 初版(依据 `stage_raw` 判 gate)
- 冒烟脚本 `scripts/smoke_m1.sh`:启动 dev server,用 curl 对着 vite proxy 验证项目 CRUD + 回退往返

### 非范围(M2+ 再做)

- `/parse` 触发与轮询、分镜/角色/场景/渲染/导出的 AI 生成
- 任何 `POST /api/v1/projects/{id}/shots/*` / `/characters/*` / `/scenes/*` / `/exports` 端点
- 版本回退 UI(`RenderVersionHistory`)、批量渲染、导出
- 真实 AI job 的进度轮询(只留 `useJobPolling` 接口)
- 登录鉴权、多人协作、i18n、主题切换

---

## 文件结构(M1 交付的所有文件)

**新建**:

```
frontend/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tsconfig.node.json
├── index.html
├── .env.development
├── .env.production
├── .eslintrc.cjs
├── .prettierrc.json
├── .gitignore
├── scripts/
│   └── smoke_m1.sh
├── README.md
└── src/
    ├── main.ts
    ├── App.vue
    ├── router/
    │   └── index.ts
    ├── api/
    │   ├── client.ts
    │   ├── projects.ts
    │   └── jobs.ts
    ├── composables/
    │   ├── useJobPolling.ts
    │   ├── useToast.ts
    │   ├── useConfirm.ts
    │   └── useStageGate.ts
    ├── store/
    │   ├── projects.ts
    │   ├── workbench.ts
    │   └── jobs.ts
    ├── types/
    │   ├── api.ts
    │   └── index.ts
    ├── utils/
    │   └── error.ts
    ├── views/
    │   ├── ProjectListView.vue
    │   ├── ProjectCreateView.vue
    │   └── WorkbenchView.vue
    ├── components/
    │   ├── layout/
    │   │   ├── AppTopbar.vue
    │   │   └── SidebarProjects.vue
    │   ├── common/
    │   │   ├── PanelSection.vue
    │   │   ├── Modal.vue
    │   │   ├── Toast.vue
    │   │   ├── StatusPill.vue
    │   │   └── ProgressBar.vue
    │   ├── setup/
    │   │   └── ProjectSetupPanel.vue
    │   ├── storyboard/
    │   │   └── StoryboardPanel.vue
    │   ├── character/
    │   │   └── CharacterAssetsPanel.vue
    │   ├── scene/
    │   │   └── SceneAssetsPanel.vue
    │   ├── generation/
    │   │   └── GenerationPanel.vue
    │   ├── export/
    │   │   └── ExportPanel.vue
    │   └── workflow/
    │       ├── WorkflowStepNav.vue
    │       └── StageRollbackModal.vue
    └── styles/
        ├── global.css
        ├── variables.css
        └── panels.css
└── tests/
    ├── unit/
    │   ├── error.spec.ts
    │   ├── useJobPolling.spec.ts
    │   └── useStageGate.spec.ts
    └── setup.ts
```

**修改**:无(从零起步;`product/workbench-demo/` 保留不动,作为样式/组件参考)。

**责任**:
- `api/client.ts`:axios 实例 + interceptor 解包 `{code, message, data}`,抛 `ApiError`
- `api/projects.ts`:对齐后端 spec §6.2 的 CRUD + rollback 端点
- `api/jobs.ts`:`GET /jobs/{id}` 接口(M1 仅定义类型和函数,不被组件触发调用)
- `composables/useJobPolling.ts`:轮询空壳,按 spec §6.3 签名,M1 单测覆盖退避/终态/cancel
- `composables/useStageGate.ts`:按 spec §8 返回 computed flags,M1 只用 `canRollback` / `canEditStoryboards`,其余留接口
- `store/projects.ts`:项目列表态
- `store/workbench.ts`:重写 demo 原 store,读后端聚合详情
- `store/jobs.ts`:活跃 job 注册表(M1 无真实 job,仅接口)
- `views/*`:三段式路由页
- `components/layout/*`:顶栏 + 左侧项目栏(接 `projectsStore` 替换 demo 的 mock)
- `components/common/*`:`Modal` / `Toast` / `ProgressBar` / `StatusPill` 通用件
- `components/workflow/StageRollbackModal.vue`:触发 `POST /rollback`
- `scripts/smoke_m1.sh`:启动 dev + curl 验证

---

## 实施前提

- 已安装 Node 20+、pnpm 9+
- 已安装 `jq`(仅 `frontend/scripts/smoke_m1.sh` 解析 JSON 时使用)
- Backend M1 已启动在 `http://127.0.0.1:8000`,且 `MYSQL_DATABASE` 里至少可创建/删除项目(走 `backend/scripts/smoke_m1.sh` 可提前验证)
- 所有命令**相对 repo 根目录**,除非显式 `cd frontend`
- 路径别名 `@/` → `src/`,与 demo 一致,避免 import 相对路径地狱
- `frontend/package.json` 的 `name` 与 `product/workbench-demo/` 明确区隔,避免 IDE 模块混淆

---

## Task 1: 初始化 frontend/ 脚手架

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/index.html`
- Create: `frontend/.env.development`
- Create: `frontend/.env.production`
- Create: `frontend/.gitignore`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`

- [ ] **Step 1: 建目录与 package.json**

```bash
mkdir -p frontend/{src/{router,api,composables,store,types,utils,views,components/{layout,common,setup,storyboard,character,scene,generation,export,workflow},styles},tests/unit,scripts}
```

```json
// frontend/package.json
{
  "name": "comic-drama-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build",
    "preview": "vite preview --port 4173",
    "typecheck": "vue-tsc --noEmit",
    "lint": "eslint 'src/**/*.{ts,vue}'",
    "format": "prettier -w 'src/**/*.{ts,vue,css}'",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "axios": "^1.7.7",
    "pinia": "^2.2.4",
    "vue": "^3.5.13",
    "vue-router": "^4.5.0"
  },
  "devDependencies": {
    "@types/node": "^22.7.5",
    "@vitejs/plugin-vue": "^5.2.1",
    "@vue/test-utils": "^2.4.6",
    "@typescript-eslint/eslint-plugin": "^8.10.0",
    "@typescript-eslint/parser": "^8.10.0",
    "eslint": "^8.57.1",
    "eslint-plugin-vue": "^9.29.0",
    "happy-dom": "^15.7.4",
    "prettier": "^3.3.3",
    "typescript": "^5.7.3",
    "vite": "^6.0.5",
    "vitest": "^2.1.3",
    "vue-tsc": "^2.2.0"
  }
}
```

- [ ] **Step 2: Vite / TS 配置**

```ts
// frontend/vite.config.ts
import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) }
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/static": { target: "http://127.0.0.1:8000", changeOrigin: true }
    }
  },
  test: {
    environment: "happy-dom",
    globals: true,
    setupFiles: ["tests/setup.ts"]
  }
});
```

```json
// frontend/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "jsx": "preserve",
    "useDefineForClassFields": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "forceConsistentCasingInFileNames": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "types": ["vite/client", "vitest/globals"],
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }
  },
  "include": ["src/**/*.ts", "src/**/*.d.ts", "src/**/*.vue", "tests/**/*.ts"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

```json
// frontend/tsconfig.node.json
{
  "compilerOptions": {
    "composite": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 3: 环境变量与 index.html**

```
# frontend/.env.development
VITE_API_BASE_URL=/api/v1
```

```
# frontend/.env.production
VITE_API_BASE_URL=/api/v1
```

```html
<!-- frontend/index.html -->
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>漫剧生成工作台</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

```
# frontend/.gitignore
node_modules/
dist/
.vite/
.env.local
*.log
coverage/
.DS_Store
```

- [ ] **Step 4: main.ts / App.vue 占位**

```ts
// frontend/src/main.ts
import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import router from "./router";
import "./styles/variables.css";
import "./styles/global.css";
import "./styles/panels.css";

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.mount("#app");
```

```vue
<!-- frontend/src/App.vue -->
<script setup lang="ts"></script>
<template>
  <RouterView />
</template>
```

占位 router(Task 11 会补全):

```ts
// frontend/src/router/index.ts
import { createRouter, createWebHistory } from "vue-router";
export default createRouter({
  history: createWebHistory(),
  routes: [{ path: "/", redirect: "/projects" }]
});
```

- [ ] **Step 5: 安装依赖与占位样式文件**

```bash
cd frontend && pnpm install
```

先建 3 个空样式文件避免 `main.ts` import 失败:

```bash
touch frontend/src/styles/{global.css,variables.css,panels.css}
```

- [ ] **Step 6: 冒烟启动 + 构建**

```bash
cd frontend && pnpm dev &
sleep 3
curl -sf http://127.0.0.1:5173 -o /dev/null && echo "dev ok"
kill %1

cd frontend && pnpm typecheck && pnpm build
```

Expected: `dev ok`,`pnpm build` 无报错,`dist/` 产出。

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/vite.config.ts \
        frontend/tsconfig.json frontend/tsconfig.node.json frontend/index.html \
        frontend/.env.development frontend/.env.production frontend/.gitignore \
        frontend/src/main.ts frontend/src/App.vue frontend/src/router/index.ts \
        frontend/src/styles/global.css frontend/src/styles/variables.css frontend/src/styles/panels.css
git commit -m "feat(frontend): 初始化前端工程(Vite+Vue3+TS+Router+Pinia+Axios)"
```

---

## Task 2: 样式迁移(global.css + variables.css + panels.css)

**Files:**
- Modify: `frontend/src/styles/variables.css`
- Modify: `frontend/src/styles/global.css`
- Modify: `frontend/src/styles/panels.css`

把 `product/workbench-demo/src/styles/global.css` 逐段拆到 `frontend/src/styles/`:

- `variables.css`:`:root` 自定义属性(颜色、间距、圆角)
- `global.css`:body/html 重置、`.page-shell` / `.topbar` / `.workspace-layout` / `.workflow-nav` 等布局类
- `panels.css`:`.panel` / `.panel-head` / `.panel-kicker` / `.status-pill` / `.card` / 各 panel 专用类

- [ ] **Step 1: 先看原 demo 样式总量**

```bash
wc -l product/workbench-demo/src/styles/global.css
```

- [ ] **Step 2: 提取变量层**

从 demo 的 `:root` 块整体抽到 `frontend/src/styles/variables.css`,补缺失变量:

```css
/* frontend/src/styles/variables.css */
:root {
  /* 继承 demo 已有色板 */
  --bg-gradient: radial-gradient(120% 120% at 10% 0%, #1a1c2e 0%, #0b0d1a 55%, #05060d 100%);
  --panel-bg: rgba(26, 28, 52, 0.72);
  --panel-border: rgba(255, 255, 255, 0.08);
  --accent: #8a8cff;
  --accent-dim: rgba(138, 140, 255, 0.2);
  --text-primary: #f0f1ff;
  --text-muted: rgba(240, 241, 255, 0.68);
  --text-faint: rgba(240, 241, 255, 0.42);

  /* M1 新增(demo 未定义但本期要用) */
  --danger: #f05a5a;
  --success: #5cd6a9;
  --warning: #f1a34b;

  --radius-lg: 18px;
  --radius-md: 12px;
  --radius-sm: 8px;

  --space-xs: 6px;
  --space-sm: 10px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 40px;
}
```

- [ ] **Step 3: 复制布局层到 global.css**

把 demo 的全局布局、topbar、workspace-layout、workflow-nav、overview-callout 等非 panel 专属样式整段拷到 `global.css`,**保持原类名**(`.page-shell` / `.topbar` / `.workflow-chip` 等)。

- [ ] **Step 4: 复制 panel 专属样式到 panels.css**

剩下的 panel/card/status-pill/dot 等迁到 `panels.css`。

- [ ] **Step 5: 冒烟**

```bash
cd frontend && pnpm build
```

Expected: 无 CSS 解析错误。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/styles/
git commit -m "feat(frontend): 迁移 workbench-demo 样式(variables/global/panels 三分)"
```

---

## Task 3: 类型定义(对齐后端 spec §13)

**Files:**
- Create: `frontend/src/types/api.ts`
- Create: `frontend/src/types/index.ts`

- [ ] **Step 1: API 层类型**

```ts
// frontend/src/types/api.ts
export interface Envelope<T> {
  code: number;
  message: string;
  data: T;
}

// 后端 spec §14 错误码
export const ERROR_CODE = {
  VALIDATION: 40001,
  STAGE_FORBIDDEN: 40301,
  NOT_FOUND: 40401,
  CONFLICT: 40901,
  RATE_LIMIT: 42901,
  INTERNAL: 50001,
  UPSTREAM: 50301
} as const;

export type ErrorCode = (typeof ERROR_CODE)[keyof typeof ERROR_CODE];

export type ProjectStageRaw =
  | "draft"
  | "storyboard_ready"
  | "characters_locked"
  | "scenes_locked"
  | "rendering"
  | "ready_for_export"
  | "exported";

export type ProjectStageZh =
  | "草稿中"
  | "分镜已生成"
  | "角色已锁定"
  | "场景已匹配"
  | "镜头生成中"
  | "待导出"
  | "已导出";

export interface ProjectSummary {
  id: string;
  name: string;
  stage: ProjectStageZh;
  stage_raw: ProjectStageRaw;
  genre: string | null;
  ratio: string;
  storyboard_count: number;
  character_count: number;
  scene_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectListResponse {
  items: ProjectSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProjectCreateRequest {
  name: string;
  story: string;
  genre?: string | null;
  ratio?: string;
  setup_params?: string[] | null;
}

export interface ProjectCreateResponse {
  id: string;
  stage: ProjectStageRaw;
  created_at: string;
}

export interface ProjectUpdateRequest {
  name?: string;
  genre?: string | null;
  ratio?: string;
  setup_params?: string[] | null;
}

export interface ProjectRollbackRequest {
  to_stage: ProjectStageRaw;
}

export interface ProjectRollbackResponse {
  from_stage: ProjectStageRaw;
  to_stage: ProjectStageRaw;
  invalidated: {
    shots_reset: number;
    characters_unlocked: number;
    scenes_unlocked: number;
  };
}

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "canceled";

export interface JobState {
  id: string;
  kind: string;
  status: JobStatus;
  progress: number;
  total: number | null;
  done: number;
  result: unknown | null;
  error_msg: string | null;
  created_at: string;
  finished_at: string | null;
}
```

- [ ] **Step 2: 领域模型类型(对齐前端 spec §9.1)**

```ts
// frontend/src/types/index.ts
import type { ProjectStageRaw, ProjectStageZh } from "./api";

export type RenderStatus = "success" | "processing" | "warning" | "failed";
export type SceneTheme = "theme-palace" | "theme-academy" | "theme-harbor";

export interface StoryboardShot {
  id: string;
  index: number;
  title: string;
  description: string;
  detail: string;
  duration: string;
  tags: string[];
}

export interface CharacterAsset {
  id: string;
  name: string;
  role: string;
  summary: string;
  description: string;
  meta: string[];
}

export interface SceneAsset {
  id: string;
  name: string;
  summary: string;
  usage: string;
  description: string;
  meta: string[];
  theme: SceneTheme;
}

export interface RenderQueueItem {
  id: string;
  title: string;
  summary: string;
  status: RenderStatus;
}

export interface ExportTask {
  id: string;
  name: string;
  summary: string;
  status: RenderStatus;
  progressLabel: string;
}

export interface ProjectData {
  id: string;
  name: string;
  stage: ProjectStageZh;
  stage_raw: ProjectStageRaw;
  genre: string | null;
  ratio: string;
  suggestedShots: string;
  story: string;
  summary: string;
  parsedStats: string[];
  setupParams: string[];
  projectOverview: string;
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

- [ ] **Step 3: 冒烟**

```bash
cd frontend && pnpm typecheck
```

Expected: 无报错。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/
git commit -m "feat(frontend): 类型定义(API envelope + ProjectData + JobState)"
```

---

## Task 4: Axios 客户端 + ApiError + 错误码映射

**Files:**
- Create: `frontend/src/utils/error.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/tests/unit/error.spec.ts`
- Create: `frontend/tests/setup.ts`

- [ ] **Step 1: 先写错误码映射的单测**

```ts
// frontend/tests/setup.ts
// 空占位,future vitest setup 入口
```

```ts
// frontend/tests/unit/error.spec.ts
import { describe, it, expect } from "vitest";
import { ApiError, messageFor } from "@/utils/error";

describe("ApiError", () => {
  it("from envelope keeps code/message/data", () => {
    const err = new ApiError(40301, "forbidden", { foo: "bar" });
    expect(err.code).toBe(40301);
    expect(err.message).toBe("forbidden");
    expect(err.data).toEqual({ foo: "bar" });
  });

  it("isNetwork for falsy code", () => {
    const err = ApiError.network("network down");
    expect(err.code).toBe(0);
    expect(err.isNetwork).toBe(true);
  });
});

describe("messageFor", () => {
  it("maps known codes to chinese text", () => {
    expect(messageFor(40001)).toMatch(/参数/);
    expect(messageFor(40301)).toMatch(/阶段/);
    expect(messageFor(40401)).toMatch(/不存在/);
    expect(messageFor(42901)).toMatch(/限流/);
    expect(messageFor(50001)).toMatch(/服务异常/);
  });

  it("falls back for unknown code", () => {
    expect(messageFor(99999)).toMatch(/未知/);
  });
});
```

- [ ] **Step 2: 跑测试失败**

```bash
cd frontend && pnpm test
```

Expected: 测试失败,提示 `Cannot find module '@/utils/error'`

- [ ] **Step 3: 实现 error.ts**

```ts
// frontend/src/utils/error.ts
import type { AxiosError } from "axios";
import { ERROR_CODE, type ErrorCode } from "@/types/api";

export class ApiError extends Error {
  readonly code: number;
  readonly data: unknown;
  readonly isNetwork: boolean;

  constructor(code: number, message: string, data?: unknown, isNetwork = false) {
    super(message);
    this.code = code;
    this.data = data;
    this.isNetwork = isNetwork;
  }

  static network(msg = "网络连接失败"): ApiError {
    return new ApiError(0, msg, null, true);
  }

  static fromAxios(err: AxiosError): ApiError {
    const body = err.response?.data as { code?: number; message?: string; data?: unknown } | undefined;
    if (body && typeof body.code === "number") {
      return new ApiError(body.code, body.message ?? "服务异常", body.data);
    }
    if (err.code === "ECONNABORTED" || err.message === "Network Error") {
      return ApiError.network(err.message);
    }
    return new ApiError(ERROR_CODE.INTERNAL, err.message || "未知错误");
  }
}

const TEXT: Record<number, string> = {
  [ERROR_CODE.VALIDATION]: "参数不合法,请检查后重试",
  [ERROR_CODE.STAGE_FORBIDDEN]: "当前阶段不允许该操作",
  [ERROR_CODE.NOT_FOUND]: "资源不存在或已被删除",
  [ERROR_CODE.CONFLICT]: "业务冲突,请刷新后重试",
  [ERROR_CODE.RATE_LIMIT]: "AI 限流,请稍后重试",
  [ERROR_CODE.INTERNAL]: "服务异常,请稍后再试",
  [ERROR_CODE.UPSTREAM]: "上游服务异常,请稍后再试"
};

export function messageFor(code: number | ErrorCode, fallback?: string): string {
  return TEXT[code] ?? fallback ?? "未知错误";
}
```

- [ ] **Step 4: 实现 axios 客户端**

```ts
// frontend/src/api/client.ts
import axios, { type AxiosInstance } from "axios";
import { ApiError } from "@/utils/error";
import type { Envelope } from "@/types/api";

export const client: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 15_000,
  headers: { "Content-Type": "application/json" }
});

client.interceptors.response.use(
  (resp) => {
    const body = resp.data as Envelope<unknown> | undefined;
    if (body && typeof body.code === "number") {
      if (body.code === 0) {
        // 改写 resp.data 为裸 data,下游直接拿
        (resp as { data: unknown }).data = body.data;
        return resp;
      }
      return Promise.reject(new ApiError(body.code, body.message ?? "error", body.data));
    }
    return resp;
  },
  (err) => Promise.reject(ApiError.fromAxios(err))
);
```

- [ ] **Step 5: 测试通过**

```bash
cd frontend && pnpm test
```

Expected: 所有测试通过(4 个测试用例)。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/utils/error.ts frontend/src/api/client.ts frontend/tests/unit/error.spec.ts frontend/tests/setup.ts
git commit -m "feat(frontend): axios 客户端 + ApiError + 错误码映射"
```

---

## Task 5: API 层(projects + jobs)

**Files:**
- Create: `frontend/src/api/projects.ts`
- Create: `frontend/src/api/jobs.ts`

- [ ] **Step 1: projects.ts**

```ts
// frontend/src/api/projects.ts
import { client } from "./client";
import type {
  ProjectCreateRequest,
  ProjectCreateResponse,
  ProjectListResponse,
  ProjectRollbackRequest,
  ProjectRollbackResponse,
  ProjectUpdateRequest
} from "@/types/api";
import type { ProjectData } from "@/types";

export const projectsApi = {
  list(params?: { page?: number; page_size?: number }): Promise<ProjectListResponse> {
    return client.get("/projects", { params }).then((r) => r.data as ProjectListResponse);
  },
  create(payload: ProjectCreateRequest): Promise<ProjectCreateResponse> {
    return client.post("/projects", payload).then((r) => r.data as ProjectCreateResponse);
  },
  get(id: string): Promise<ProjectData> {
    return client.get(`/projects/${id}`).then((r) => r.data as ProjectData);
  },
  update(id: string, payload: ProjectUpdateRequest): Promise<ProjectData> {
    return client.patch(`/projects/${id}`, payload).then((r) => r.data as ProjectData);
  },
  remove(id: string): Promise<{ deleted: boolean }> {
    return client.delete(`/projects/${id}`).then((r) => r.data as { deleted: boolean });
  },
  rollback(id: string, payload: ProjectRollbackRequest): Promise<ProjectRollbackResponse> {
    return client.post(`/projects/${id}/rollback`, payload).then((r) => r.data as ProjectRollbackResponse);
  }
};
```

- [ ] **Step 2: jobs.ts(M1 接口占位,给 composable 用)**

```ts
// frontend/src/api/jobs.ts
import { client } from "./client";
import type { JobState } from "@/types/api";

export const jobsApi = {
  get(id: string, signal?: AbortSignal): Promise<JobState> {
    return client.get(`/jobs/${id}`, { signal }).then((r) => r.data as JobState);
  }
};
```

> 注:后端 M1 尚未实现 `GET /jobs/{id}`(M2 补);M1 仅提供 client 函数,**不触发调用**,以便 useJobPolling 可单测。组件侧无真实调用。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/projects.ts frontend/src/api/jobs.ts
git commit -m "feat(frontend): api/projects + api/jobs 端点封装"
```

---

## Task 6: useJobPolling(空壳,可单测)

**Files:**
- Create: `frontend/src/composables/useJobPolling.ts`
- Create: `frontend/tests/unit/useJobPolling.spec.ts`

- [ ] **Step 1: 先写测试**

测试用假 `fetcher` 替换真实 `jobsApi.get`,验证:退避步进、终态立即停止、cancel 清理、同一 job 多次激活只有一条轮询。

```ts
// frontend/tests/unit/useJobPolling.spec.ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ref } from "vue";
import { useJobPolling } from "@/composables/useJobPolling";
import type { JobState } from "@/types/api";

const baseJob: JobState = {
  id: "j1", kind: "parse_novel", status: "running",
  progress: 10, total: 100, done: 10, result: null,
  error_msg: null, created_at: "", finished_at: null
};

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("useJobPolling", () => {
  it("polls at 2s, stops on success terminal state", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce({ ...baseJob, progress: 30 })
      .mockResolvedValueOnce({ ...baseJob, progress: 60 })
      .mockResolvedValueOnce({ ...baseJob, status: "succeeded", progress: 100 });
    const onSuccess = vi.fn();
    const onError = vi.fn();

    const jobId = ref<string | null>("j1");
    useJobPolling(jobId, { onSuccess, onError }, fetcher);

    await vi.advanceTimersByTimeAsync(2100);
    await vi.advanceTimersByTimeAsync(2100);
    await vi.advanceTimersByTimeAsync(2100);

    expect(fetcher).toHaveBeenCalledTimes(3);
    expect(onSuccess).toHaveBeenCalledOnce();
    expect(onError).not.toHaveBeenCalled();
  });

  it("backs off 2s -> 4s -> 8s when no progress", async () => {
    const same = { ...baseJob };
    const fetcher = vi.fn().mockResolvedValue(same);
    const jobId = ref<string | null>("j1");
    useJobPolling(jobId, { onSuccess: () => {}, onError: () => {} }, fetcher);

    for (let i = 0; i < 3; i++) await vi.advanceTimersByTimeAsync(2100);
    expect(fetcher).toHaveBeenCalledTimes(3);
    for (let i = 0; i < 3; i++) await vi.advanceTimersByTimeAsync(4100);
    expect(fetcher).toHaveBeenCalledTimes(6);
    await vi.advanceTimersByTimeAsync(8100);
    expect(fetcher).toHaveBeenCalledTimes(7);
  });

  it("null jobId stops polling", async () => {
    const fetcher = vi.fn().mockResolvedValue(baseJob);
    const jobId = ref<string | null>("j1");
    const { cancel } = useJobPolling(jobId, { onSuccess: () => {}, onError: () => {} }, fetcher);

    await vi.advanceTimersByTimeAsync(2100);
    cancel();
    await vi.advanceTimersByTimeAsync(10_000);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: 实现 composable**

```ts
// frontend/src/composables/useJobPolling.ts
import { getCurrentInstance, onUnmounted, ref, watch, type Ref } from "vue";
import { jobsApi } from "@/api/jobs";
import type { JobState } from "@/types/api";

export type JobFetcher = (id: string, signal?: AbortSignal) => Promise<JobState>;

export interface JobPollingHandlers {
  onProgress?: (job: JobState) => void;
  onSuccess: (job: JobState) => void;
  onError: (job: JobState | null, err?: unknown) => void;
}

interface JobPollingHandle {
  job: Ref<JobState | null>;
  cancel: () => void;
}

const TERMINAL = new Set(["succeeded", "failed", "canceled"]);
const INTERVALS = [2000, 4000, 8000];
const BACKOFF_AFTER = 3;

export function useJobPolling(
  jobId: Ref<string | null>,
  handlers: JobPollingHandlers,
  fetcher: JobFetcher = jobsApi.get
): JobPollingHandle {
  const job = ref<JobState | null>(null);
  let timer: ReturnType<typeof setTimeout> | null = null;
  let stage = 0;
  let sameCount = 0;
  let lastProgress = -1;
  let aborter: AbortController | null = null;

  const cancel = () => {
    if (timer) { clearTimeout(timer); timer = null; }
    if (aborter) { aborter.abort(); aborter = null; }
  };

  const tick = async (id: string) => {
    aborter = new AbortController();
    try {
      const next = await fetcher(id, aborter.signal);
      job.value = next;
      handlers.onProgress?.(next);

      if (TERMINAL.has(next.status)) {
        cancel();
        if (next.status === "succeeded") handlers.onSuccess(next);
        else handlers.onError(next);
        return;
      }

      if (next.progress === lastProgress) sameCount++;
      else { sameCount = 0; lastProgress = next.progress; }
      if (sameCount >= BACKOFF_AFTER && stage < INTERVALS.length - 1) {
        stage++; sameCount = 0;
      }
      timer = setTimeout(() => tick(id), INTERVALS[stage]);
    } catch (err) {
      handlers.onError(job.value, err);
      cancel();
    }
  };

  watch(jobId, (id) => {
    cancel();
    stage = 0; sameCount = 0; lastProgress = -1; job.value = null;
    if (id) timer = setTimeout(() => tick(id), INTERVALS[0]);
  }, { immediate: true });

  if (getCurrentInstance()) onUnmounted(cancel);

  return { job, cancel };
}
```

- [ ] **Step 3: 测试通过**

```bash
cd frontend && pnpm test
```

Expected: 新增 3 个测试用例全部通过。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/composables/useJobPolling.ts frontend/tests/unit/useJobPolling.spec.ts
git commit -m "feat(frontend): useJobPolling(轮询骨架 + 退避/终态/cancel 单测)"
```

---

## Task 7: useStageGate(M1 初版)

**Files:**
- Create: `frontend/src/composables/useStageGate.ts`
- Create: `frontend/tests/unit/useStageGate.spec.ts`

- [ ] **Step 1: 测试(纯函数版本,脱离 store)**

```ts
// frontend/tests/unit/useStageGate.spec.ts
import { describe, it, expect } from "vitest";
import { gateFlags } from "@/composables/useStageGate";

describe("gateFlags", () => {
  it("draft: only rollback is false, edit allowed", () => {
    const g = gateFlags("draft");
    expect(g.canEditStoryboards).toBe(true);
    expect(g.canGenerateCharacters).toBe(false);
    expect(g.canRollback).toBe(false);
  });

  it("storyboard_ready: edit + characters gen allowed", () => {
    const g = gateFlags("storyboard_ready");
    expect(g.canEditStoryboards).toBe(true);
    expect(g.canGenerateCharacters).toBe(true);
    expect(g.canRollback).toBe(true);
  });

  it("rendering: render allowed, export not", () => {
    const g = gateFlags("rendering");
    expect(g.canRender).toBe(true);
    expect(g.canExport).toBe(false);
    expect(g.canLockShot).toBe(true);
  });

  it("exported: all write gates false, rollback true", () => {
    const g = gateFlags("exported");
    expect(g.canEditStoryboards).toBe(false);
    expect(g.canExport).toBe(false);
    expect(g.canRollback).toBe(true);
  });

  it("null stage: all false", () => {
    const g = gateFlags(null);
    expect(g.canRollback).toBe(false);
    expect(g.canEditStoryboards).toBe(false);
  });
});
```

- [ ] **Step 2: 实现**

```ts
// frontend/src/composables/useStageGate.ts
import { computed } from "vue";
import { storeToRefs } from "pinia";
import { useWorkbenchStore } from "@/store/workbench";
import type { ProjectStageRaw } from "@/types/api";

export interface StageGateFlags {
  canEditStoryboards: boolean;
  canGenerateCharacters: boolean;
  canGenerateScenes: boolean;
  canRender: boolean;
  canExport: boolean;
  canLockShot: boolean;
  canRollback: boolean;
}

export function gateFlags(raw: ProjectStageRaw | null | undefined): StageGateFlags {
  return {
    canEditStoryboards: raw === "draft" || raw === "storyboard_ready",
    canGenerateCharacters: raw === "storyboard_ready",
    canGenerateScenes: raw === "characters_locked",
    canRender: raw === "scenes_locked" || raw === "rendering",
    canExport: raw === "ready_for_export",
    canLockShot: raw === "rendering" || raw === "ready_for_export",
    canRollback: !!raw && raw !== "draft"
  };
}

export function useStageGate() {
  const { current } = storeToRefs(useWorkbenchStore());
  const flags = computed(() => gateFlags(current.value?.stage_raw ?? null));
  return { flags };
}
```

- [ ] **Step 3: 测试通过**

```bash
cd frontend && pnpm test
```

Expected: 新增 5 个测试用例全部通过。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/composables/useStageGate.ts frontend/tests/unit/useStageGate.spec.ts
git commit -m "feat(frontend): useStageGate + gateFlags 纯函数 + 单测"
```

---

## Task 8: Toast / Confirm / Modal 三件套

**Files:**
- Create: `frontend/src/composables/useToast.ts`
- Create: `frontend/src/composables/useConfirm.ts`
- Create: `frontend/src/components/common/Toast.vue`
- Create: `frontend/src/components/common/Modal.vue`
- Create: `frontend/src/components/common/ProgressBar.vue`
- Create: `frontend/src/components/common/StatusPill.vue`
- Create: `frontend/src/components/common/PanelSection.vue`

- [ ] **Step 1: useToast**

```ts
// frontend/src/composables/useToast.ts
import { reactive } from "vue";

export type ToastVariant = "info" | "success" | "warning" | "error";
export interface ToastAction { label: string; onClick: () => void }
export interface ToastItem {
  id: number;
  variant: ToastVariant;
  message: string;
  detail?: string;
  action?: ToastAction;
}

const store = reactive({ items: [] as ToastItem[] });
let seq = 1;

function push(variant: ToastVariant, message: string, opts?: { detail?: string; action?: ToastAction; persist?: boolean }) {
  const id = seq++;
  store.items.push({ id, variant, message, detail: opts?.detail, action: opts?.action });
  const ttl = opts?.persist ? 0 : variant === "error" ? 5000 : 3000;
  if (ttl > 0) setTimeout(() => dismiss(id), ttl);
  return id;
}

function dismiss(id: number) {
  const i = store.items.findIndex((t) => t.id === id);
  if (i >= 0) store.items.splice(i, 1);
}

export function useToast() {
  return {
    items: store.items,
    info: (m: string, o?: Parameters<typeof push>[2]) => push("info", m, o),
    success: (m: string, o?: Parameters<typeof push>[2]) => push("success", m, o),
    warning: (m: string, o?: Parameters<typeof push>[2]) => push("warning", m, o),
    error: (m: string, o?: Parameters<typeof push>[2]) => push("error", m, o),
    dismiss
  };
}
```

- [ ] **Step 2: Toast.vue(全局单例渲染)**

```vue
<!-- frontend/src/components/common/Toast.vue -->
<script setup lang="ts">
import { useToast } from "@/composables/useToast";
const toast = useToast();
</script>
<template>
  <div class="toast-stack">
    <div v-for="t in toast.items" :key="t.id" :class="['toast', `toast-${t.variant}`]">
      <div class="toast-body">
        <p class="toast-msg">{{ t.message }}</p>
        <p v-if="t.detail" class="toast-detail">{{ t.detail }}</p>
      </div>
      <button v-if="t.action" class="toast-action" @click="t.action!.onClick">{{ t.action.label }}</button>
      <button class="toast-close" @click="toast.dismiss(t.id)">×</button>
    </div>
  </div>
</template>
<style scoped>
.toast-stack { position: fixed; top: 24px; right: 24px; display: flex; flex-direction: column; gap: 10px; z-index: 900; max-width: 360px; }
.toast { display: flex; gap: 10px; padding: 12px 14px; border-radius: var(--radius-md); background: var(--panel-bg); border: 1px solid var(--panel-border); color: var(--text-primary); backdrop-filter: blur(14px); }
.toast-success { border-color: var(--success); }
.toast-error { border-color: var(--danger); }
.toast-warning { border-color: var(--warning); }
.toast-msg { margin: 0; font-size: 14px; }
.toast-detail { margin: 4px 0 0; font-size: 12px; color: var(--text-muted); }
.toast-action { background: transparent; border: 1px solid var(--accent); color: var(--accent); padding: 4px 10px; border-radius: var(--radius-sm); cursor: pointer; }
.toast-close { background: transparent; border: none; color: var(--text-faint); cursor: pointer; font-size: 18px; }
</style>
```

- [ ] **Step 3: Modal.vue(受控)**

```vue
<!-- frontend/src/components/common/Modal.vue -->
<script setup lang="ts">
defineProps<{ open: boolean; title?: string; danger?: boolean }>();
defineEmits<{ (e: "close"): void }>();
</script>
<template>
  <div v-if="open" class="modal-scrim" @click.self="$emit('close')">
    <div class="modal-card">
      <header class="modal-head">
        <h3 :class="{ danger }">{{ title }}</h3>
        <button @click="$emit('close')">×</button>
      </header>
      <div class="modal-body"><slot /></div>
      <footer class="modal-foot"><slot name="footer" /></footer>
    </div>
  </div>
</template>
<style scoped>
.modal-scrim { position: fixed; inset: 0; background: rgba(5, 6, 13, 0.72); display: grid; place-items: center; z-index: 800; }
.modal-card { min-width: 420px; max-width: 560px; background: var(--panel-bg); border: 1px solid var(--panel-border); border-radius: var(--radius-lg); padding: 20px; color: var(--text-primary); backdrop-filter: blur(14px); }
.modal-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.modal-head h3.danger { color: var(--danger); }
.modal-head button { background: transparent; border: none; color: var(--text-faint); font-size: 20px; cursor: pointer; }
.modal-body { font-size: 14px; color: var(--text-muted); line-height: 1.6; }
.modal-foot { display: flex; gap: 10px; justify-content: flex-end; margin-top: 18px; }
</style>
```

- [ ] **Step 4: useConfirm(基于 Modal 的 Promise 化确认框)**

```ts
// frontend/src/composables/useConfirm.ts
import { reactive } from "vue";

export interface ConfirmOptions {
  title: string;
  body?: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
}
interface ConfirmState extends ConfirmOptions {
  open: boolean;
  resolve: ((ok: boolean) => void) | null;
}

const state = reactive<ConfirmState>({
  open: false, title: "", body: "", confirmText: "确认", cancelText: "取消", danger: false, resolve: null
});

export function useConfirmState() { return state; }

export function confirm(opts: ConfirmOptions): Promise<boolean> {
  return new Promise((resolve) => {
    Object.assign(state, {
      open: true,
      title: "",
      body: "",
      confirmText: "确认",
      cancelText: "取消",
      danger: false,
      resolve,
      ...opts
    });
  });
}

export function resolveConfirm(ok: boolean) {
  state.open = false;
  state.resolve?.(ok);
  state.resolve = null;
}
```

- [ ] **Step 5: ProgressBar / StatusPill / PanelSection 三个小件**

迁移 demo 的 `PanelSection.vue` 到 `components/common/PanelSection.vue`(原样),另写两个小件:

```vue
<!-- frontend/src/components/common/ProgressBar.vue -->
<script setup lang="ts">
defineProps<{ value?: number; indeterminate?: boolean }>();
</script>
<template>
  <div class="pbar">
    <div v-if="indeterminate" class="pbar-indet" />
    <div v-else class="pbar-fill" :style="{ width: `${Math.min(100, Math.max(0, value ?? 0))}%` }" />
  </div>
</template>
<style scoped>
.pbar { height: 6px; background: rgba(255,255,255,0.06); border-radius: 3px; overflow: hidden; }
.pbar-fill { height: 100%; background: var(--accent); transition: width 240ms ease; }
.pbar-indet { height: 100%; width: 35%; background: var(--accent); animation: pbar-slide 1.2s ease-in-out infinite; }
@keyframes pbar-slide { 0% { transform: translateX(-100%); } 100% { transform: translateX(300%); } }
</style>
```

```vue
<!-- frontend/src/components/common/StatusPill.vue -->
<script setup lang="ts">
defineProps<{ tone?: "success" | "warning" | "danger" | "info"; text: string }>();
</script>
<template>
  <span :class="['status-pill', `tone-${tone ?? 'info'}`]">
    <span class="dot" /> {{ text }}
  </span>
</template>
<style scoped>
.status-pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; font-size: 12px; border-radius: 999px; background: rgba(255,255,255,0.06); color: var(--text-muted); }
.status-pill .dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.tone-success { color: var(--success); }
.tone-warning { color: var(--warning); }
.tone-danger { color: var(--danger); }
.tone-info { color: var(--accent); }
</style>
```

> `PanelSection.vue` 直接从 `product/workbench-demo/src/components/PanelSection.vue` 原样拷贝,调整 `@/` 别名即可。

- [ ] **Step 6: App.vue 挂 Toast + Confirm**

```vue
<!-- frontend/src/App.vue -->
<script setup lang="ts">
import Toast from "@/components/common/Toast.vue";
import Modal from "@/components/common/Modal.vue";
import { useConfirmState, resolveConfirm } from "@/composables/useConfirm";
const state = useConfirmState();
</script>
<template>
  <RouterView />
  <Toast />
  <Modal :open="state.open" :title="state.title" :danger="state.danger" @close="resolveConfirm(false)">
    <p>{{ state.body }}</p>
    <template #footer>
      <button class="ghost-btn" @click="resolveConfirm(false)">{{ state.cancelText }}</button>
      <button :class="['primary-btn', { danger: state.danger }]" @click="resolveConfirm(true)">{{ state.confirmText }}</button>
    </template>
  </Modal>
</template>
```

- [ ] **Step 7: 构建冒烟**

```bash
cd frontend && pnpm typecheck && pnpm test
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/composables/useToast.ts frontend/src/composables/useConfirm.ts \
        frontend/src/components/common/ frontend/src/App.vue
git commit -m "feat(frontend): Toast/Modal/Confirm 三件套与 PanelSection/ProgressBar/StatusPill"
```

---

## Task 9: Pinia stores

**Files:**
- Create: `frontend/src/store/projects.ts`
- Create: `frontend/src/store/workbench.ts`
- Create: `frontend/src/store/jobs.ts`

- [ ] **Step 1: projects store(列表态)**

```ts
// frontend/src/store/projects.ts
import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { projectsApi } from "@/api/projects";
import type { ProjectCreateRequest, ProjectSummary } from "@/types/api";
import { ApiError } from "@/utils/error";

export const useProjectsStore = defineStore("projects", () => {
  const list = ref<ProjectSummary[]>([]);
  const total = ref(0);
  const loading = ref(false);
  const keyword = ref("");

  const filtered = computed(() => {
    const kw = keyword.value.trim().toLowerCase();
    if (!kw) return list.value;
    return list.value.filter((p) => p.name.toLowerCase().includes(kw));
  });

  const metrics = computed(() => [
    { label: "项目总数", value: `${total.value} 个` },
    { label: "待导出", value: `${list.value.filter((p) => p.stage_raw === "ready_for_export").length} 个` },
    { label: "已完成", value: `${list.value.filter((p) => p.stage_raw === "exported").length} 个` }
  ]);

  async function fetchList(page = 1, pageSize = 50) {
    loading.value = true;
    try {
      const resp = await projectsApi.list({ page, page_size: pageSize });
      list.value = resp.items;
      total.value = resp.total;
    } finally {
      loading.value = false;
    }
  }

  async function createProject(payload: ProjectCreateRequest) {
    const resp = await projectsApi.create(payload);
    await fetchList();
    return resp;
  }

  async function deleteProject(id: string) {
    await projectsApi.remove(id);
    list.value = list.value.filter((p) => p.id !== id);
    total.value = Math.max(0, total.value - 1);
  }

  function applyFilter(kw: string) { keyword.value = kw; }

  function isApiError(e: unknown): e is ApiError { return e instanceof ApiError; }

  return { list, total, loading, keyword, filtered, metrics, fetchList, createProject, deleteProject, applyFilter, isApiError };
});
```

- [ ] **Step 2: workbench store(详情 + 选中态)**

```ts
// frontend/src/store/workbench.ts
import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { projectsApi } from "@/api/projects";
import type { ProjectData } from "@/types";
import type { ProjectRollbackRequest, ProjectRollbackResponse } from "@/types/api";

export type WorkflowStep = "setup" | "storyboard" | "character" | "scene" | "render" | "export";

export const useWorkbenchStore = defineStore("workbench", () => {
  const current = ref<ProjectData | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const selectedShotId = ref<string>("");
  const selectedCharacterId = ref<string>("");
  const selectedSceneId = ref<string>("");
  const activeStep = ref<WorkflowStep>("setup");

  const currentShot = computed(() =>
    current.value?.storyboards.find((s) => s.id === selectedShotId.value) ?? current.value?.storyboards[0] ?? null
  );
  const selectedCharacter = computed(() =>
    current.value?.characters.find((c) => c.id === selectedCharacterId.value) ?? current.value?.characters[0] ?? null
  );
  const selectedScene = computed(() =>
    current.value?.scenes.find((s) => s.id === selectedSceneId.value) ?? current.value?.scenes[0] ?? null
  );

  async function load(id: string) {
    loading.value = true; error.value = null;
    try {
      current.value = await projectsApi.get(id);
      selectedShotId.value = current.value.storyboards[0]?.id ?? "";
      selectedCharacterId.value = current.value.characters[0]?.id ?? "";
      selectedSceneId.value = current.value.scenes[0]?.id ?? "";
    } catch (e) {
      error.value = (e as Error).message;
      throw e;
    } finally {
      loading.value = false;
    }
  }

  async function reload() { if (current.value) await load(current.value.id); }

  async function rollback(payload: ProjectRollbackRequest): Promise<ProjectRollbackResponse> {
    if (!current.value) throw new Error("no current project");
    const resp = await projectsApi.rollback(current.value.id, payload);
    await reload();
    return resp;
  }

  function selectShot(id: string) { selectedShotId.value = id; }
  function selectCharacter(id: string) { selectedCharacterId.value = id; }
  function selectScene(id: string) { selectedSceneId.value = id; }
  function setStep(step: WorkflowStep) { activeStep.value = step; }

  return {
    current, loading, error,
    selectedShotId, selectedCharacterId, selectedSceneId, activeStep,
    currentShot, selectedCharacter, selectedScene,
    load, reload, rollback,
    selectShot, selectCharacter, selectScene, setStep
  };
});
```

- [ ] **Step 3: jobs store(骨架,M1 无真实 job 但保留接口)**

```ts
// frontend/src/store/jobs.ts
import { defineStore } from "pinia";
import { reactive } from "vue";
import type { JobState } from "@/types/api";

interface Entry {
  job: JobState | null;
  cancel: () => void;
}

export const useJobsStore = defineStore("jobs", () => {
  const byId = reactive<Record<string, Entry>>({});

  function register(id: string, cancel: () => void) {
    byId[id] = { job: null, cancel };
  }
  function update(id: string, job: JobState) {
    if (byId[id]) byId[id].job = job;
  }
  function stop(id: string) {
    byId[id]?.cancel();
    delete byId[id];
  }
  function isActive(id: string) { return !!byId[id]; }

  return { byId, register, update, stop, isActive };
});
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/store/
git commit -m "feat(frontend): pinia stores(projects/workbench/jobs,职责不重叠)"
```

---

## Task 10: 迁移 demo 业务 panel 到 frontend

**Files:**
- Create: `frontend/src/components/layout/SidebarProjects.vue`
- Create: `frontend/src/components/layout/AppTopbar.vue`
- Create: `frontend/src/components/workflow/WorkflowStepNav.vue`
- Create: `frontend/src/components/setup/ProjectSetupPanel.vue`
- Create: `frontend/src/components/storyboard/StoryboardPanel.vue`
- Create: `frontend/src/components/character/CharacterAssetsPanel.vue`
- Create: `frontend/src/components/scene/SceneAssetsPanel.vue`
- Create: `frontend/src/components/generation/GenerationPanel.vue`
- Create: `frontend/src/components/export/ExportPanel.vue`

**原则**:
- 以 `product/workbench-demo/src/components/*.vue` 为基底原样拷贝,拆到业务域目录
- `useWorkbenchStore()` 源头已从 mock 换成真实 `ProjectData`,模板用 `current` 而非 `currentProject`
- demo 原先直接迭代 `currentProject.storyboards` 等,在 M1 真实后端返回空数组时渲染为空态;**每个 panel 要加 `v-if="current" + 空态提示**
- M1 不改视觉样式,类名 1:1 保留

- [ ] **Step 1: SidebarProjects(接 projectsStore)**

```vue
<!-- frontend/src/components/layout/SidebarProjects.vue -->
<script setup lang="ts">
import { onMounted } from "vue";
import { storeToRefs } from "pinia";
import { useRouter } from "vue-router";
import { useProjectsStore } from "@/store/projects";

const store = useProjectsStore();
const { filtered, metrics, keyword } = storeToRefs(store);
const router = useRouter();

onMounted(() => { void store.fetchList(); });

function open(id: string) { void router.push({ name: "workbench", params: { id } }); }
</script>
<template>
  <aside class="sidebar">
    <header>
      <p class="eyebrow">项目</p>
      <input v-model="keyword" placeholder="搜索项目" class="search" />
    </header>
    <ul class="project-list">
      <li v-for="p in filtered" :key="p.id" @click="open(p.id)">
        <div class="card-mini">
          <p class="name">{{ p.name }}</p>
          <p class="meta">{{ p.stage }} · {{ p.storyboard_count }} 镜头</p>
        </div>
      </li>
      <li v-if="!filtered.length" class="empty">暂无项目</li>
    </ul>
    <footer class="metrics">
      <div v-for="m in metrics" :key="m.label" class="metric">
        <span>{{ m.label }}</span>
        <strong>{{ m.value }}</strong>
      </div>
    </footer>
  </aside>
</template>
<style scoped>
.sidebar { display: flex; flex-direction: column; gap: 18px; padding: 20px; background: var(--panel-bg); border-radius: var(--radius-lg); border: 1px solid var(--panel-border); min-width: 260px; }
.search { width: 100%; background: rgba(255,255,255,0.04); border: 1px solid var(--panel-border); color: var(--text-primary); padding: 8px 10px; border-radius: var(--radius-sm); }
.project-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
.card-mini { padding: 10px 12px; border-radius: var(--radius-md); cursor: pointer; }
.card-mini:hover { background: rgba(138, 140, 255, 0.08); }
.card-mini .name { margin: 0 0 4px; font-weight: 600; color: var(--text-primary); }
.card-mini .meta { margin: 0; font-size: 12px; color: var(--text-muted); }
.empty { color: var(--text-faint); font-size: 13px; padding: 12px 0; text-align: center; }
.metrics { display: flex; justify-content: space-between; border-top: 1px solid var(--panel-border); padding-top: 12px; }
.metric { display: flex; flex-direction: column; font-size: 12px; color: var(--text-muted); gap: 2px; }
.metric strong { color: var(--text-primary); font-size: 14px; }
</style>
```

- [ ] **Step 2: AppTopbar + WorkflowStepNav**

```vue
<!-- frontend/src/components/layout/AppTopbar.vue -->
<script setup lang="ts">
defineProps<{ title?: string; subtitle?: string }>();
</script>
<template>
  <header class="topbar">
    <div>
      <p class="eyebrow">Comic Drama Platform</p>
      <h1>{{ title ?? "漫剧生成工作台" }}</h1>
      <p v-if="subtitle" class="subtitle">{{ subtitle }}</p>
    </div>
    <div class="topbar-actions"><slot /></div>
  </header>
</template>
```

```vue
<!-- frontend/src/components/workflow/WorkflowStepNav.vue -->
<script setup lang="ts">
import type { WorkflowStep } from "@/store/workbench";
const steps: { key: WorkflowStep; label: string }[] = [
  { key: "setup", label: "新建项目" },
  { key: "storyboard", label: "分镜工作台" },
  { key: "character", label: "角色设定" },
  { key: "scene", label: "场景设定" },
  { key: "render", label: "镜头生成" },
  { key: "export", label: "导出" }
];
defineProps<{ active: WorkflowStep }>();
defineEmits<{ (e: "change", step: WorkflowStep): void }>();
</script>
<template>
  <nav class="workflow-nav">
    <button v-for="s in steps" :key="s.key" :class="['workflow-chip', { active: active === s.key }]"
            type="button" @click="$emit('change', s.key)">
      {{ s.label }}
    </button>
  </nav>
</template>
```

- [ ] **Step 3: 六个业务 Panel 原样迁移**

对每个 demo 组件按以下映射迁移:

| Demo 组件 | 目标路径 |
| --- | --- |
| `ProjectSetupPanel.vue` | `frontend/src/components/setup/ProjectSetupPanel.vue` |
| `StoryboardPanel.vue` | `frontend/src/components/storyboard/StoryboardPanel.vue` |
| `CharacterAssetsPanel.vue` | `frontend/src/components/character/CharacterAssetsPanel.vue` |
| `SceneAssetsPanel.vue` | `frontend/src/components/scene/SceneAssetsPanel.vue` |
| `GenerationPanel.vue` | `frontend/src/components/generation/GenerationPanel.vue` |
| `ExportPanel.vue` | `frontend/src/components/export/ExportPanel.vue` |

对每个 panel 按以下步骤:
1. 从 `product/workbench-demo/src/components/<Name>.vue` 拷贝到上表目标路径
2. import 路径改 `@/store/workbench` 并把 `currentProject` 改为 `current`
3. 模板顶层加 `v-if="current"`;依赖数组数据的 panel 在数组为空时显示空态文案
4. `ProjectSetupPanel` 没有下游数组空态,但要在 `current.storyboards.length === 0` 时展示 M1 只读草稿提示,并保留 `story` / `summary` / `setupParams` 只读展示

例如 `StoryboardPanel.vue`:

```vue
<!-- frontend/src/components/storyboard/StoryboardPanel.vue -->
<script setup lang="ts">
import { storeToRefs } from "pinia";
import PanelSection from "@/components/common/PanelSection.vue";
import { useWorkbenchStore } from "@/store/workbench";

const store = useWorkbenchStore();
const { current, currentShot } = storeToRefs(store);
</script>
<template>
  <PanelSection v-if="current" kicker="02" title="分镜工作台">
    <div v-if="!current.storyboards.length" class="empty-note">
      尚未生成分镜 · M1 仅支持项目创建,分镜生成请等待 M2
    </div>
    <div v-else class="storyboard-grid">
      <!-- demo 原内容 -->
    </div>
  </PanelSection>
</template>
<style scoped>
.empty-note { padding: 40px 0; text-align: center; color: var(--text-faint); font-size: 13px; }
</style>
```

其余 5 个 panel 同理,保留 demo 的视觉结构;其中角色/场景/生成/导出 panel 在对应数组为空时显示"当前里程碑不提供"文案。

> **M1 细则**:所有"写"按钮(新增/编辑/删除/生成/锁定/渲染/导出)都**禁用 + 悬浮提示**"M1 不支持,等待 M2",避免把未实装端点暴露给用户误点。

- [ ] **Step 4: typecheck**

```bash
cd frontend && pnpm typecheck
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/
git commit -m "feat(frontend): 迁移 workbench-demo 六大 panel + 顶栏/侧栏/步骤条到业务域目录"
```

---

## Task 11: 路由 + 三段视图

**Files:**
- Modify: `frontend/src/router/index.ts`
- Create: `frontend/src/views/ProjectListView.vue`
- Create: `frontend/src/views/ProjectCreateView.vue`
- Create: `frontend/src/views/WorkbenchView.vue`

- [ ] **Step 1: router**

```ts
// frontend/src/router/index.ts
import { createRouter, createWebHistory } from "vue-router";

const ProjectListView = () => import("@/views/ProjectListView.vue");
const ProjectCreateView = () => import("@/views/ProjectCreateView.vue");
const WorkbenchView = () => import("@/views/WorkbenchView.vue");

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/projects" },
    { path: "/projects", name: "project-list", component: ProjectListView },
    { path: "/projects/new", name: "project-new", component: ProjectCreateView },
    { path: "/projects/:id", name: "workbench", component: WorkbenchView, props: true }
  ]
});

export default router;
```

- [ ] **Step 2: ProjectListView**

```vue
<!-- frontend/src/views/ProjectListView.vue -->
<script setup lang="ts">
import { onMounted } from "vue";
import { storeToRefs } from "pinia";
import { useRouter } from "vue-router";
import AppTopbar from "@/components/layout/AppTopbar.vue";
import { useProjectsStore } from "@/store/projects";
import { useToast } from "@/composables/useToast";
import { confirm } from "@/composables/useConfirm";
import { ApiError } from "@/utils/error";
import { messageFor } from "@/utils/error";

const store = useProjectsStore();
const { filtered, loading, keyword, metrics } = storeToRefs(store);
const router = useRouter();
const toast = useToast();

onMounted(async () => {
  try { await store.fetchList(); } catch (e) { toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "加载失败"); }
});

async function remove(id: string, name: string) {
  const ok = await confirm({ title: "删除项目?", body: `「${name}」的所有镜头、资产、导出任务将一并删除。`, confirmText: "确认删除", danger: true });
  if (!ok) return;
  try { await store.deleteProject(id); toast.success("已删除"); }
  catch (e) { toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "删除失败"); }
}
</script>
<template>
  <div class="page-shell">
    <AppTopbar title="我的项目" subtitle="管理所有漫剧项目">
      <button class="primary-btn" @click="$router.push({ name: 'project-new' })">新建项目</button>
    </AppTopbar>
    <section class="list-head">
      <input v-model="keyword" placeholder="按名称搜索" class="search" />
      <div class="metrics">
        <span v-for="m in metrics" :key="m.label"><b>{{ m.value }}</b> {{ m.label }}</span>
      </div>
    </section>
    <section class="project-grid">
      <article v-for="p in filtered" :key="p.id" class="project-card" @click="router.push({ name: 'workbench', params: { id: p.id } })">
        <header>
          <span class="stage">{{ p.stage }}</span>
          <h3>{{ p.name }}</h3>
        </header>
        <p class="meta">{{ p.storyboard_count }} 个镜头 · {{ p.character_count }} 角色 · {{ p.scene_count }} 场景</p>
        <footer>
          <time>{{ new Date(p.updated_at).toLocaleString("zh-CN") }}</time>
          <button class="danger-link" @click.stop="remove(p.id, p.name)">删除</button>
        </footer>
      </article>
      <p v-if="!loading && !filtered.length" class="empty">暂无项目,从右上角新建</p>
    </section>
  </div>
</template>
<style scoped>
/* 复用 global.css / panels.css 的基调;局部增量 */
.list-head { display: flex; justify-content: space-between; margin: 18px 0; gap: 18px; }
.search { flex: 0 0 280px; background: var(--panel-bg); border: 1px solid var(--panel-border); color: var(--text-primary); padding: 8px 12px; border-radius: var(--radius-sm); }
.metrics { display: flex; gap: 24px; color: var(--text-muted); font-size: 13px; }
.metrics b { color: var(--text-primary); margin-right: 4px; }
.project-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.project-card { padding: 18px; background: var(--panel-bg); border: 1px solid var(--panel-border); border-radius: var(--radius-lg); cursor: pointer; transition: border-color 160ms; }
.project-card:hover { border-color: var(--accent); }
.project-card .stage { font-size: 12px; color: var(--accent); }
.project-card h3 { margin: 6px 0 10px; color: var(--text-primary); }
.project-card .meta { color: var(--text-muted); font-size: 13px; margin: 0 0 12px; }
.project-card footer { display: flex; justify-content: space-between; font-size: 12px; color: var(--text-faint); }
.danger-link { background: transparent; border: none; color: var(--danger); cursor: pointer; }
.empty { grid-column: 1 / -1; text-align: center; color: var(--text-faint); padding: 48px 0; }
.primary-btn { padding: 8px 16px; border-radius: var(--radius-sm); border: none; background: var(--accent); color: #0b0d1a; font-weight: 600; cursor: pointer; }
</style>
```

- [ ] **Step 3: ProjectCreateView**

```vue
<!-- frontend/src/views/ProjectCreateView.vue -->
<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import AppTopbar from "@/components/layout/AppTopbar.vue";
import { useProjectsStore } from "@/store/projects";
import { useToast } from "@/composables/useToast";
import { ApiError, messageFor } from "@/utils/error";

const form = ref({ name: "", story: "", genre: "古风权谋", ratio: "9:16" });
const loading = ref(false);
const router = useRouter();
const toast = useToast();
const store = useProjectsStore();

const canSubmit = computed(() => form.value.name.trim() && form.value.story.trim().length >= 200);

async function submit() {
  if (!canSubmit.value) return;
  loading.value = true;
  try {
    const resp = await store.createProject({
      name: form.value.name.trim(),
      story: form.value.story.trim(),
      genre: form.value.genre,
      ratio: form.value.ratio
    });
    toast.success("项目已创建");
    await router.push({ name: "workbench", params: { id: resp.id } });
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "创建失败");
  } finally {
    loading.value = false;
  }
}
</script>
<template>
  <div class="page-shell">
    <AppTopbar title="新建项目">
      <button class="ghost-btn" @click="$router.back()">返回</button>
    </AppTopbar>
    <form class="create-form" @submit.prevent="submit">
      <label>
        <span>项目名</span>
        <input v-model="form.name" maxlength="128" placeholder="如:皇城夜雨" />
      </label>
      <label>
        <span>题材</span>
        <select v-model="form.genre">
          <option>古风权谋</option><option>学院科幻</option><option>都市悬疑</option><option>其他</option>
        </select>
      </label>
      <label>
        <span>小说正文({{ form.story.length }} 字,需 ≥ 200 字)</span>
        <textarea v-model="form.story" rows="12" placeholder="粘贴完整小说正文..." />
      </label>
      <footer>
        <button type="button" class="ghost-btn" @click="$router.back()">取消</button>
        <button type="submit" class="primary-btn" :disabled="!canSubmit || loading">
          {{ loading ? "创建中..." : "创建项目" }}
        </button>
      </footer>
      <p class="note">M1 仅创建项目;分镜解析等待 M2 上线后自动可用</p>
    </form>
  </div>
</template>
<style scoped>
.create-form { max-width: 720px; margin: 24px auto; display: flex; flex-direction: column; gap: 16px; background: var(--panel-bg); padding: 24px; border-radius: var(--radius-lg); border: 1px solid var(--panel-border); }
.create-form label { display: flex; flex-direction: column; gap: 6px; color: var(--text-muted); font-size: 13px; }
.create-form input, .create-form select, .create-form textarea { background: rgba(255,255,255,0.04); border: 1px solid var(--panel-border); color: var(--text-primary); padding: 10px 12px; border-radius: var(--radius-sm); font: inherit; }
.create-form footer { display: flex; justify-content: flex-end; gap: 10px; }
.note { font-size: 12px; color: var(--text-faint); margin: 0; }
.primary-btn { padding: 8px 16px; border-radius: var(--radius-sm); border: none; background: var(--accent); color: #0b0d1a; font-weight: 600; cursor: pointer; }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.ghost-btn { padding: 8px 16px; border-radius: var(--radius-sm); background: transparent; border: 1px solid var(--panel-border); color: var(--text-primary); cursor: pointer; }
</style>
```

- [ ] **Step 4: WorkbenchView(挂 StageRollbackModal 留在 Task 12)**

```vue
<!-- frontend/src/views/WorkbenchView.vue -->
<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import AppTopbar from "@/components/layout/AppTopbar.vue";
import SidebarProjects from "@/components/layout/SidebarProjects.vue";
import WorkflowStepNav from "@/components/workflow/WorkflowStepNav.vue";
import ProjectSetupPanel from "@/components/setup/ProjectSetupPanel.vue";
import StoryboardPanel from "@/components/storyboard/StoryboardPanel.vue";
import CharacterAssetsPanel from "@/components/character/CharacterAssetsPanel.vue";
import SceneAssetsPanel from "@/components/scene/SceneAssetsPanel.vue";
import GenerationPanel from "@/components/generation/GenerationPanel.vue";
import ExportPanel from "@/components/export/ExportPanel.vue";
import StageRollbackModal from "@/components/workflow/StageRollbackModal.vue";
import { useWorkbenchStore, type WorkflowStep } from "@/store/workbench";
import { useToast } from "@/composables/useToast";
import { ApiError, messageFor } from "@/utils/error";

const route = useRoute();
const router = useRouter();
const store = useWorkbenchStore();
const { current, loading, activeStep } = storeToRefs(store);
const toast = useToast();

const rollbackOpen = ref(false);
const subtitle = computed(() => current.value?.stage ?? "加载中");
const STEP_KEYS: WorkflowStep[] = ["setup", "storyboard", "character", "scene", "render", "export"];

async function loadCurrent() {
  try { await store.load(String(route.params.id)); }
  catch (e) {
    if (e instanceof ApiError && e.code === 40401) {
      toast.error("项目不存在");
      await router.replace({ name: "project-list" });
    } else {
      toast.error(e instanceof Error ? e.message : "加载失败");
    }
  }
}

async function changeStep(step: WorkflowStep) {
  store.setStep(step);
  await router.replace({ query: { ...route.query, step } });
  await nextTick();
  document.getElementById(`panel-${step}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

onMounted(async () => {
  await loadCurrent();
  const step = route.query.step;
  if (typeof step === "string" && STEP_KEYS.includes(step as WorkflowStep)) {
    await changeStep(step as WorkflowStep);
  }
});
watch(() => route.params.id, (id) => id && loadCurrent());
</script>
<template>
  <div class="page-shell">
    <AppTopbar :title="current?.name ?? '加载中...'" :subtitle="subtitle">
      <button class="ghost-btn" :disabled="!current" @click="rollbackOpen = true">回退阶段</button>
      <button class="ghost-btn" @click="$router.push({ name: 'project-list' })">返回列表</button>
    </AppTopbar>
    <main class="workspace-layout">
      <SidebarProjects />
      <section class="content-area">
        <WorkflowStepNav :active="activeStep" @change="changeStep" />
        <div v-if="loading" class="skeleton">正在加载项目...</div>
        <template v-else-if="current">
          <div id="panel-setup"><ProjectSetupPanel /></div>
          <div id="panel-storyboard"><StoryboardPanel /></div>
          <div id="panel-character"><CharacterAssetsPanel /></div>
          <div id="panel-scene"><SceneAssetsPanel /></div>
          <div id="panel-render"><GenerationPanel /></div>
          <div id="panel-export"><ExportPanel /></div>
        </template>
      </section>
    </main>
    <StageRollbackModal v-if="current" :open="rollbackOpen" @close="rollbackOpen = false" />
  </div>
</template>
<style scoped>
.skeleton { padding: 60px 0; text-align: center; color: var(--text-faint); }
</style>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/router/index.ts frontend/src/views/
git commit -m "feat(frontend): 三段式路由与 ProjectList/Create/Workbench 视图"
```

---

## Task 12: StageRollbackModal(联调 /rollback)

**Files:**
- Create: `frontend/src/components/workflow/StageRollbackModal.vue`

- [ ] **Step 1: Modal 实现**

```vue
<!-- frontend/src/components/workflow/StageRollbackModal.vue -->
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import Modal from "@/components/common/Modal.vue";
import { useWorkbenchStore } from "@/store/workbench";
import { useStageGate } from "@/composables/useStageGate";
import { useToast } from "@/composables/useToast";
import { ApiError, messageFor } from "@/utils/error";
import type { ProjectStageRaw } from "@/types/api";

const STAGE_OPTIONS: { value: ProjectStageRaw; label: string }[] = [
  { value: "draft", label: "草稿中" },
  { value: "storyboard_ready", label: "分镜已生成" },
  { value: "characters_locked", label: "角色已锁定" },
  { value: "scenes_locked", label: "场景已匹配" },
  { value: "rendering", label: "镜头生成中" },
  { value: "ready_for_export", label: "待导出" },
  { value: "exported", label: "已导出" }
];

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ (e: "close"): void }>();

const store = useWorkbenchStore();
const { current } = storeToRefs(store);
const { flags } = useStageGate();
const toast = useToast();

const target = ref<ProjectStageRaw>("draft");
const loading = ref(false);
const stageLabel = (stage: ProjectStageRaw) => STAGE_OPTIONS.find((o) => o.value === stage)?.label ?? stage;

const currentRaw = computed(() => current.value?.stage_raw ?? null);
const currentIdx = computed(() => STAGE_OPTIONS.findIndex((o) => o.value === currentRaw.value));
const options = computed(() => STAGE_OPTIONS.filter((_, i) => currentIdx.value > 0 && i < currentIdx.value));

watch(() => props.open, (open) => {
  if (open) {
    target.value = options.value[options.value.length - 1]?.value ?? "draft";
  }
});

async function confirm() {
  if (!flags.value.canRollback) {
    toast.warning("当前阶段不允许回退");
    return;
  }
  loading.value = true;
  try {
    const resp = await store.rollback({ to_stage: target.value });
    const inv = resp.invalidated;
    toast.success(
      `已从「${stageLabel(resp.from_stage)}」回退到「${stageLabel(resp.to_stage)}」`,
      { detail: `重置镜头 ${inv.shots_reset} 个,解锁角色 ${inv.characters_unlocked} 个,解锁场景 ${inv.scenes_unlocked} 个` }
    );
    emit("close");
  } catch (e) {
    if (e instanceof ApiError) toast.error(messageFor(e.code, e.message));
    else toast.error("回退失败");
  } finally {
    loading.value = false;
  }
}
</script>
<template>
  <Modal :open="open" title="回退阶段" danger @close="emit('close')">
    <p>当前阶段:<b>{{ current?.stage ?? "-" }}</b></p>
    <p v-if="!flags.canRollback" class="warn">当前阶段不支持回退。</p>
    <template v-else>
      <p>选择目标阶段,该阶段之后的资产将被失效并需要重做。</p>
      <select v-model="target" class="select">
        <option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>
    </template>
    <template #footer>
      <button class="ghost-btn" @click="emit('close')">取消</button>
      <button class="primary-btn danger" :disabled="!flags.canRollback || loading" @click="confirm">
        {{ loading ? "执行中..." : "我已了解,执行回退" }}
      </button>
    </template>
  </Modal>
</template>
<style scoped>
.select { width: 100%; padding: 8px 10px; background: rgba(255,255,255,0.04); border: 1px solid var(--panel-border); color: var(--text-primary); border-radius: var(--radius-sm); }
.warn { color: var(--warning); }
.primary-btn { padding: 8px 16px; border-radius: var(--radius-sm); border: none; background: var(--accent); color: #0b0d1a; font-weight: 600; cursor: pointer; }
.primary-btn.danger { background: var(--danger); color: #fff; }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.ghost-btn { padding: 8px 16px; border-radius: var(--radius-sm); background: transparent; border: 1px solid var(--panel-border); color: var(--text-primary); cursor: pointer; }
</style>
```

- [ ] **Step 2: typecheck + build**

```bash
cd frontend && pnpm typecheck && pnpm build
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workflow/StageRollbackModal.vue
git commit -m "feat(frontend): StageRollbackModal(联调 POST /projects/:id/rollback)"
```

---

## Task 13: 冒烟脚本 + README

**Files:**
- Create: `frontend/scripts/smoke_m1.sh`
- Create: `frontend/README.md`
- Create: `frontend/.eslintrc.cjs`
- Create: `frontend/.prettierrc.json`

- [ ] **Step 1: ESLint / Prettier 最小配置**

```js
// frontend/.eslintrc.cjs
module.exports = {
  root: true,
  env: { browser: true, es2022: true, node: true },
  parser: "vue-eslint-parser",
  parserOptions: { parser: "@typescript-eslint/parser", ecmaVersion: "latest", sourceType: "module" },
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:vue/vue3-recommended"
  ],
  rules: {
    "no-var": "error",
    eqeqeq: ["error", "always"],
    "vue/multi-word-component-names": "off",
    "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }]
  }
};
```

```json
// frontend/.prettierrc.json
{
  "semi": true,
  "singleQuote": false,
  "printWidth": 110,
  "trailingComma": "none"
}
```

- [ ] **Step 2: smoke 脚本**

```bash
# frontend/scripts/smoke_m1.sh
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BE=${BE:-http://127.0.0.1:8000}
FE=${FE:-http://127.0.0.1:5173}
FE_PID_FILE=${FE_PID_FILE:-/tmp/comic-drama-fe.pid}
FE_LOG_FILE=${FE_LOG_FILE:-/tmp/comic-drama-fe.log}

cleanup() {
  if [[ -f "$FE_PID_FILE" ]]; then
    FE_PID="$(cat "$FE_PID_FILE")"
    kill "$FE_PID" 2>/dev/null || true
    wait "$FE_PID" 2>/dev/null || true
    rm -f "$FE_PID_FILE"
  fi
}
trap cleanup EXIT

echo "[1/6] 后端健康检查"
curl -fsS "$BE/healthz" | jq '.data'

echo "[2/6] 前端 typecheck + build"
( cd "$REPO_ROOT/frontend" && pnpm typecheck && pnpm build )

echo "[3/6] 启动前端 dev server"
( cd "$REPO_ROOT/frontend" && exec pnpm dev >"$FE_LOG_FILE" 2>&1 ) &
echo $! > "$FE_PID_FILE"
sleep 5

echo "[4/6] 通过前端代理命中后端 /api/v1/projects"
# 创建
PID=$(curl -fsS -X POST "$FE/api/v1/projects" -H 'Content-Type: application/json' \
  -d '{"name":"前端冒烟","story":"从前有座山,山上有座庙..."}' | jq -r .data.id)
echo "created: $PID"

# 读
curl -fsS "$FE/api/v1/projects/$PID" | jq '.data | {id, stage, stage_raw, name}'

# 列
curl -fsS "$FE/api/v1/projects?page=1&page_size=50" | jq '.data.total'

echo "[5/6] rollback draft → draft(预期 403 / 40301)"
RB_BODY=$(mktemp)
RB_CODE=$(curl -s -o "$RB_BODY" -w '%{http_code}' \
  -X POST "$FE/api/v1/projects/$PID/rollback" -H 'Content-Type: application/json' \
  -d '{"to_stage":"draft"}')
jq . "$RB_BODY"
[[ "$RB_CODE" == "403" ]] || { echo "expected 403, got $RB_CODE"; exit 1; }
[[ "$(jq -r .code "$RB_BODY")" == "40301" ]] || { echo "expected body.code=40301"; exit 1; }
rm -f "$RB_BODY"

echo "[6/6] 清理"
curl -fsS -X DELETE "$FE/api/v1/projects/$PID" | jq .

echo "✅ frontend M1 smoke passed"
```

```bash
chmod +x frontend/scripts/smoke_m1.sh
```

- [ ] **Step 3: README**

```markdown
# Comic Drama Frontend (M1)

Vue 3 + Vite + TS + Pinia + Axios 工程骨架,联调后端 M1 的项目 CRUD 与 rollback 端点。

## 快速开始

\`\`\`bash
# 0. 确保后端 M1 已启动在 http://127.0.0.1:8000
# 1. 安装依赖
cd frontend && pnpm install

# 2. 日常启动 dev(代理 /api → 127.0.0.1:8000)
pnpm dev
# 访问 http://127.0.0.1:5173

# 3. 冒烟(从 repo 根目录执行;脚本会自行启动/清理 dev server)
# 注意:冒烟不需要先执行 pnpm dev;若 5173 已被手动 dev 占用,请先停止
./frontend/scripts/smoke_m1.sh
\`\`\`

## 测试

\`\`\`bash
pnpm test         # 纯逻辑单测(error / useJobPolling / useStageGate)
pnpm typecheck    # vue-tsc 全量类型检查
pnpm build        # 构建产物到 dist/
\`\`\`

## M1 已交付

- 脚手架:Vite + Vue 3 + TS + Router + Pinia + Axios
- 样式:迁移自 `product/workbench-demo/`,按 variables/global/panels 三分
- `projects` 列表 / 详情 / 创建 / 删除联调 OK
- `/rollback` 联调 OK,含非法回退的 40301 toast 映射
- `useJobPolling` / `useStageGate` 骨架 + 单测,为 M2 留接口

## M1 不包含

- 分镜解析、角色/场景资产、镜头渲染、导出 — 见 M2+
- 真实 AI job 轮询 — useJobPolling 目前只对着 mock fetcher 跑单测
- 登录鉴权 / i18n / 主题切换 — MVP 范围外

## 目录

`src/api/` 请求封装 · `src/store/` Pinia · `src/composables/` 无状态逻辑 ·
`src/views/` 页面 · `src/components/{layout,common,setup,storyboard,character,scene,generation,export,workflow}/` 业务组件 ·
`src/styles/` 全局样式 · `tests/unit/` 单测
```

- [ ] **Step 4: 全量冒烟**

```bash
(
  cd backend
  source .venv/bin/activate
  exec uvicorn app.main:app --port 8000
) &
BE_PID=$!
trap 'kill "$BE_PID" 2>/dev/null || true' EXIT
sleep 3
./frontend/scripts/smoke_m1.sh
kill "$BE_PID" 2>/dev/null || true
trap - EXIT
```

Expected: 全部 ✅,且 toast 映射 40301 时在 dev 页面能看到提示。

- [ ] **Step 5: Commit**

```bash
git add frontend/scripts/smoke_m1.sh frontend/README.md frontend/.eslintrc.cjs frontend/.prettierrc.json
git commit -m "docs(frontend): M1 冒烟脚本 + README + eslint/prettier 配置"
```

---

## 完成标准 (Definition of Done)

- [ ] `cd frontend && pnpm install && pnpm dev` 能启动,首页 `/projects` 展示后端真实项目
- [ ] `pnpm typecheck` 无错,`pnpm build` 通过 vue-tsc + vite build
- [ ] `pnpm test` 通过(覆盖 `utils/error` / `useJobPolling` / `useStageGate`)
- [ ] `./frontend/scripts/smoke_m1.sh` 一次性通过(需先启动后端)
- [ ] 浏览器手测:创建项目 → 列表可见 → 进工作台 → 六大 panel 空态正确 → 回退弹窗对 `draft` 项目显示"不支持回退",对被强制改到 `storyboard_ready` 以上的项目可成功回退并 toast 反馈
- [ ] 40001 / 40301 / 40401 / 50001 四类错误码均有 toast 文案(可通过后端 spec §14 示例手触发)
- [ ] `grep -RIn "mockProjects\|currentProject" frontend/src` 结果为空(demo 残留清零)
- [ ] `ProjectData.stage_raw` 在 workbench store 中被 gate 使用,store 与 composable 间不传中文 `stage` 做判断
- [ ] git 提交历史按任务拆分,每个 Task 至少一次 commit

---

## 自检(本 plan 写完后的 review)

- **Spec 覆盖**:前端 spec §15 M1 声明"工程脚手架 + 迁移 demo 的静态样式和组件 + 联调 projects CRUD 与 /rollback + 引入 useJobPolling 空壳"。本 plan Task 1-2(脚手架 + 样式)、Task 3-5(类型+客户端+API)、Task 6-7(useJobPolling/useStageGate)、Task 9(stores)、Task 10-12(view + panel + rollback modal)全覆盖
- **Placeholder 扫描**:全文无 TBD / TODO / "implement later" 字样
- **与后端 M1 契约**:`ProjectListResponse` / `ProjectDetail`(`stage` + `stage_raw`)/ `ProjectRollbackResponse`(`from_stage` / `to_stage` / `invalidated`)与 `docs/superpowers/plans/2026-04-20-backend-m1-skeleton.md` Task 7 / Task 10 返回完全一致;错误码 40001/40301/40401 与 Task 9 `errors.py` 一致
- **Stage gate 一致性**:`gateFlags` 的判定与前端 spec §8 表对齐;`canRollback: raw !== "draft"` 与后端 `is_rollback_allowed`(要求 `target_idx < current_idx`,`draft` 无更小 idx)逻辑一致,避免前端按钮亮但后端 403
- **视觉不漂移**:Task 2 仅拷样式文件,Task 10 强制原样拷 panel 组件,类名 1:1;新增的列表页/新建页用了与 demo 同调的颜色变量

---

## 衔接下一份 plan

- **Frontend M2**:对接后端 M2 的 `/parse` + `/storyboards/*`,`ProjectSetupPanel` 的"开始拆分分镜"按钮打通 → 轮询主 job → 渲染分镜卡片;`StoryboardPanel` 的新增/编辑/删除/确认流程联调;`useJobPolling` 改为真实挂载;阶段门在"分镜未确认"时锁定下游 panel
- **关联依赖**:M2 前端开始前,后端 M2 plan(`2026-04-21-backend-m2-pipeline-and-mock.md`)需先交付 `POST /api/v1/projects/{id}/parse` 与 `GET /api/v1/jobs/{id}` 两个端点 + mock VolcanoClient
