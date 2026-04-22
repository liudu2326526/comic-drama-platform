# BUG 记录文档

本文档用于记录在产品演示与测试过程中发现的问题。

## 未解决的 BUG

### 1. 小说拆分分镜状态显示异常
- **描述**：在“新建项目”页面点击“开始拆分分镜”按钮后，界面会显示进度条（例如“正在解析小说... 10%”）。但随后进度条会消失，界面重新变回“开始拆分分镜”的初始按钮状态。
- **实际行为**：后台 Celery 任务仍在正常运行。等待一段时间（约 30-60 秒）任务完成后，界面会直接跳过中间状态，变为解析完成并显示摘要。
- **期望行为**：进度条应持续显示直至任务完成或失败，不应中途跳回初始按钮状态。
- **根本原因**：
    1. “拆分分镜”实际上由两个连续的 AI 任务组成：`parse_novel`（解析梗概/角色数）和 `gen_storyboard`（生成分镜列表）。
    2. 前端 `SetupPanel.vue` 只监听了 `parse_novel` 任务。
    3. 当 `parse_novel` 完成后，前端调用 `markParseSucceeded()` 将 `activeParseJobId` 置为空。
    4. 此时 `gen_storyboard` 仍在运行，数据库中分镜数量仍为 0。
    5. 前端计算属性 `canStartParse` 判定条件（`stage === 'draft' && storyboards.length === 0 && !activeParseJobId`）再次成立，导致界面回退到初始按钮。
- **修复建议**：
    - 方案 A：后端将两个任务合并为一个 Job，或者让 `parse_novel` 任务等待 `gen_storyboard` 完成后再返回（会占用 worker 时间，不推荐）。
    - 方案 B：前端在 `parse_novel` 成功后，自动开始轮询该项目的 `gen_storyboard` 任务（推荐）。
- **发现日期**：2026-04-22
- **状态**：已修复 (Fixed)
- **修复说明**：
    1. 在 Pinia Store (`workbench.ts`) 中增加了对 `gen_storyboard` 任务的追踪状态。
    2. 在 `SetupPanel.vue` 中增加了对 `gen_storyboard` 任务的轮询逻辑。
    3. 当 `parse_novel` 任务成功后，前端会自动通过 `findAndTrackGenStoryboardJob` 寻找并开始轮询紧随其后的 `gen_storyboard` 任务，从而保持进度条的连续显示。

### 2. 角色/场景生成接口超时 (timeout of 15000ms exceeded)
- **描述**：点击“生成角色资产”或“生成场景资产”后，界面弹出红框报错 `timeout of 15000ms exceeded`。但刷新页面或等待一段时间后，角色/场景实际上已经生成成功并显示在列表中。
- **实际行为**：前端 Axios 默认超时设置为 15s。在 `real` AI 模式下，AI 提取角色/场景列表（同步请求）往往需要 20-40s。前端请求虽然中断报错，但后端任务仍在继续执行并最终落库。
- **期望行为**：对于耗时较长的 AI 提取操作，前端应允许更长的等待时间，或者后端应将其完全异步化。
- **初步分析**：`POST /characters/generate` 和 `POST /scenes/generate` 接口中的 AI 提取逻辑是同步执行的，超出了前端 15s 的硬限制。
- **发现日期**：2026-04-22
- **状态**：已修复 (Fixed)
- **修复说明**：
    1. 在前端 API 层（`characters.ts` 和 `scenes.ts`）中，为 `generate` 和 `regenerate` 接口单独设置了 60s 的超时时间。
    2. 这确保了即使 AI 提取逻辑耗时较长，前端请求也不会被过早中断，从而避免了“报错但实际生成成功”的尴尬状态。


