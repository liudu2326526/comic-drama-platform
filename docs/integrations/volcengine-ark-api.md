# 火山方舟(Volcengine Ark)API 集成文档

> **覆盖范围**
> 1. 私域虚拟人像资产库(Asset / AssetGroup)
> 2. 视频生成 Seedance(创建 / 查询 / 列表 / 取消或删除)
> 3. 图片生成 Seedream
> 4. 对话(Chat)Doubao
>
> 基于 `docs/huoshan_api/*.md` 中火山官方文档整理,用于本项目后端对接。
> **本项目场景**:Chat 做剧本改写与素材理解;Image 做分镜/封面;Video 做最终渲染;**人像库用来把固定主角的参考形象上传到平台,再在 Seedance 2.0 视频请求里以 `asset://<id>` 的形式复用,避免每次上传 + 绕开 deepfake 拦截**。

---

## 0. 通用说明与分域

### 0.1 两套完全不同的 API 域

| 接口分组 | Host | 鉴权 | 调用方式 |
|---|---|---|---|
| Chat / 图片 / 视频生成(四件套) | `ark.cn-beijing.volces.com` | **API Key**(`Authorization: Bearer <ARK_API_KEY>`) | RESTful,`/api/v3/...` 路径直写 |
| **人像库(Asset/AssetGroup)** | `ark.cn-beijing.volcengineapi.com` | **AK/SK HMAC-SHA256 签名** | OpenAPI 风格,`Action=xxx&Version=2024-01-01` 走 query,Path 固定 `/` |

⚠️ **不要混用**。前者是长效 API Key;后者必须走 IAM AK/SK。实现上建议分两个 Python client 文件。

### 0.2 凭据环境变量约定

```
ARK_API_KEY=sk-xxxxx              # 走 Chat/Image/Video,Bearer 鉴权
VOLC_ACCESS_KEY_ID=AKLTxxxxx      # 走人像库,HMAC 签名
VOLC_SECRET_ACCESS_KEY=xxxxx      # 同上
ARK_PROJECT_NAME=default          # 人像库资源所属项目,必须与 API Key 的项目一致
```

### 0.3 项目(Project)隔离

- 人像库的 `Asset` / `AssetGroup` 都绑定 `ProjectName`(不传默认为 `default`)。
- **硬约束**:向 `AssetGroup` 内创建 `Asset` 时,两者 `ProjectName` 必须一致;用 `asset://<id>` 调视频生成时,调用所用的 API Key 所属项目也必须一致。否则视频生成找不到这个 asset。
- 本项目 MVP 统一使用 `default` 项目,后续多租户再按 `ProjectName = tenant-<id>` 切分。

### 0.4 SDK 兼容性

- Chat / Image 走 OpenAI 兼容,直接 `openai.OpenAI(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=ARK_API_KEY)`。
- 视频生成(Seedance)不在 OpenAI Spec 中,火山提供 `volcengine-python-sdk`:
  ```python
  from volcenginesdkarkruntime import Ark
  client = Ark(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=os.environ["ARK_API_KEY"])
  client.content_generation.tasks.create(model=..., content=[...])
  ```
- 人像库没有 Python SDK,需自行实现 HMAC 签名(参考 §1.7 demo)。

### 0.5 时间与过期

| 资源 | 生命周期 |
|---|---|
| 视频生成任务 ID | 保留 **7 天**(从 `created_at` 起),过期自动清除 |
| 视频 `video_url` / `last_frame_url` | 生成后 **24 小时** |
| 图片 `data[].url` | 生成后 **24 小时** |
| 人像库 Asset URL(GetAsset 返回) | **12 小时** |

所有 URL **必须在过期前 fetch 回源到项目自有 OSS**(推荐 TOS 数据订阅自动转存)。业务表只能存自有 OSS URL。

---

## 1. 人像库(Asset / AssetGroup)API

### 1.1 概念

- **AssetGroup**:一组关联素材的管理单位,建议"同一角色的不同参考图/视频/音频归入同一 Group"。
- **Asset**:一个素材文件(图 / 视频 / 音频)。必须属于某个 Group。
- **推理只能用 `Status = Active` 的 Asset**;`Processing` 不能用,`Failed` 永久失败。
- 在视频生成请求里通过 `asset://<ASSET_ID>` 引用。

### 1.2 鉴权

火山 OpenAPI 风格,`AK/SK + HMAC-SHA256` 签名。**必填 Header**:

- `Host: ark.cn-beijing.volcengineapi.com`
- `X-Date: 20260421T120000Z`(UTC, 无标点)
- `X-Content-Sha256: <SHA256(body)>`
- `Content-Type: application/json`
- `Authorization: HMAC-SHA256 Credential=<AK>/20260421/cn-beijing/ark/request, SignedHeaders=content-type;host;x-content-sha256;x-date, Signature=<hex>`

**固定 Query**:`Action=<xxx>&Version=2024-01-01`(加上用户传的 query 后按 key 字典序排序、URL 编码再参与签名)。

签名流程参见 `docs/huoshan_api/人像库 demo/CreateAssetGroup_Demo.py`(本项目直接复用其 `request_api()` 函数即可)。

### 1.3 素材格式要求(图像类)

| 项 | 值 |
|---|---|
| 格式 | jpeg / png / webp / bmp / tiff / gif / heic / heif |
| 宽高比 | (0.4, 2.5) |
| 宽高像素 | (300, 6000) |
| 单张大小 | < 30 MB |
| 最佳实践 | 全身参考图(竖版正面全身)+ 人脸特写(竖版,正面无表情,面部占画面 2/3),归入同一 Group |

视频/音频素材要求见 §2.1 表格中的参考素材限制。

### 1.4 限流

| 接口 | 限流 |
|---|---|
| CreateAssetGroup | 10 QPS |
| CreateAsset | 300 QPM |
| ListAssetGroups / ListAssets | 10 QPS |
| GetAsset | 100 QPS |
| GetAssetGroup | 10 QPS |
| UpdateAsset / UpdateAssetGroup | 10 QPS |
| DeleteAsset | 10 QPS |
| DeleteAssetGroup | 5 QPS |

本项目轮询 `GetAsset` 等待素材 Active,**间隔 ≥ 3s**(demo 默认 3s,超时 120s),避免触发 100 QPS 上限。

### 1.5 接口清单

| Action | 用途 | 关键入参 | 返回 |
|---|---|---|---|
| `CreateAssetGroup` | 创建素材组 | `Name`, `Description`, `GroupType`(默认 `AIGC`,当前只支持该值), `ProjectName` | `{ "Id": "group-YYYYMMDD...-xxxxx" }` |
| `CreateAsset` | 上传单个素材(异步,无 SLA) | `GroupId`(必填), `URL`(必填,公网 URL), `AssetType`(必填,`Image`/`Video`/`Audio`), `Name`(选填), `ProjectName`(选填) | `{ "Id": "asset-YYYYMMDD...-xxxxx" }` |
| `GetAsset` | 查询单个素材状态 | `Id`, `ProjectName` | 见下方响应 |
| `GetAssetGroup` | 查询单个素材组 | `Id`, `ProjectName` | 组信息 |
| `ListAssets` | 分页查询素材 | `Filter.GroupIds[]` / `Filter.GroupType` / `Filter.Statuses[]`(`Active`/`Processing`/`Failed`) / `Filter.Name`(模糊), `PageNumber`, `PageSize`, `SortBy`, `SortOrder` | `{ Items: [...], TotalCount, PageNumber, PageSize }` |
| `ListAssetGroups` | 分页查询素材组 | `Filter.Name`(模糊) / `Filter.GroupIds[]` / `Filter.GroupType`, `PageNumber`, `PageSize` | 同上 |
| `UpdateAsset` | 更新素材(Name) | `Id`, `Name` | - |
| `UpdateAssetGroup` | 更新素材组 | `Id`, `Name`, `Description` | - |
| `DeleteAsset` | 删除素材 | `Id` | - |
| `DeleteAssetGroup` | 删除素材组 | `Id` | - |

### 1.6 GetAsset 响应

```json
{
  "Id": "asset-20260318035710-xxxxx",
  "GroupId": "group-20260318033332-xxxxx",
  "Status": "Active",
  "AssetType": "Image",
  "Name": "",
  "URL": "https://ark-media-asset.tos-cn-beijing.volces.com/.../xxx.jpg?X-Tos-Expires=43200&...",
  "ProjectName": "default",
  "CreateTime": "2026-03-18T03:57:10Z",
  "UpdateTime": "2026-03-18T03:57:14Z"
}
```

| 字段 | 说明 |
|---|---|
| `Status` | `Processing` / `Active` / `Failed`。**仅 Active 可用于推理** |
| `URL` | **有效期 12 小时**(X-Tos-Expires=43200 秒) |
| `CreateTime` / `UpdateTime` | ISO 8601 UTC |

### 1.7 本项目接入流程(推荐)

```
用户在前端上传角色参考图
  ↓
后端 POST 到自家 OSS(先有自己的持久 URL)
  ↓
CreateAssetGroup(如果该角色第一张图)→ 得 group_id,存 DB
  ↓
CreateAsset(GroupId, URL=自家 OSS URL, AssetType=Image)→ 得 asset_id
  ↓
起一个后台 worker,每 3s 调一次 GetAsset,直到 Status=Active 或超过 120s
  ↓
写入本项目 DB: characters.avatar_asset_id = asset_id
  ↓
后续所有含该角色的视频生成,content[] 里用 {"type":"image_url","image_url":{"url":"asset://<asset_id>"},"role":"reference_image"}
```

### 1.8 在 Prompt 中引用素材的规则

**重要**:Seedance 2.0 要求在文本 prompt 中用"**图片 1 / 视频 1 / 音频 1**"指代参考素材,序号 = 该素材在 `content[]` 中同类型的顺序。**禁止在 prompt 里直接写 asset ID**。

示例(1 个文本 + 5 张参考图 + 1 段参考音频):

```
图片 1 里的女孩穿着图片 2 的衣服,走向图片 3 中的男孩,两人在图片 4 的雨夜共撑黑伞,
背景画面右下角出现图片 5 的文字水印,语气参考音频 1 的情感色彩……
```

---

## 2. 视频生成 API(Seedance 系列)

Base:`https://ark.cn-beijing.volces.com/api/v3`,Bearer 鉴权。

支持模型:
- `doubao-seedance-2-0-260128` / `doubao-seedance-2-0-fast-*`(推荐,支持多模态参考、有声视频、可用人像库 asset)
- `doubao-seedance-1-5-pro-251215`(支持 draft 模式)
- `doubao-seedance-1-0-pro-*` / `doubao-seedance-1-0-pro-fast-*`
- `doubao-seedance-1-0-lite-t2v` / `doubao-seedance-1-0-lite-i2v-250428`

### 2.1 创建任务 `POST /contents/generations/tasks`

#### 顶层参数

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `model` | string | 是 | - | Model ID 或 Endpoint ID |
| `content` | object[] | 是 | - | 内容数组,见下方 §2.1.1 |
| `callback_url` | string | 否 | - | 任务状态变化时 POST,payload 与查询任务返回一致;5s 内无 200 响应则重试 3 次 |
| `return_last_frame` | bool | 否 | `false` | 是否返回尾帧 PNG(无水印) |
| `service_tier` | string | 否 | `default` | `default`(在线) / `flex`(离线,价格 50%,2.0 系列不支持) |
| `execution_expires_after` | int | 否 | `172800`(48h) | 任务超时秒数,范围 `[3600, 259200]`,超时后状态变 `expired` |
| `generate_audio` | bool | 否 | `true` | 仅 2.0/2.0-fast/1.5-pro 支持;对话推荐用双引号包裹,如 `说:"..."` |
| `draft` | bool | 否 | `false` | 仅 1.5-pro;开启后 480p 预览,不支持尾帧/离线 |
| `tools` | object[] | 否 | - | 仅 2.0/2.0-fast,如 `[{"type":"web_search"}]` |
| `safety_identifier` | string | 否 | - | 终端用户哈希 ID,≤64 字符 |
| **`resolution`** | string | 否 | `720p`(2.0/2.0-fast/1.5/1.0-lite);`1080p`(1.0-pro) | `480p` / `720p` / `1080p`(2.0-fast 与 1.0-lite 参考图场景不支持 1080p) |
| **`ratio`** | string | 否 | 2.0/1.5-pro = `adaptive`;文生视频 = `16:9`;图生视频 = `adaptive` | `16:9` / `4:3` / `1:1` / `3:4` / `9:16` / `21:9` / `adaptive` |
| **`duration`** | int | 否 | `5` | 2.0/2.0-fast:`[4, 15]` 或 `-1`(模型自选);1.5-pro:`[4, 12]` 或 `-1`;1.0 系列:`[2, 12]` |
| **`frames`** | int | 否 | - | 与 `duration` 二选一,`frames` 优先级高;取值 `25 + 4n`,范围 `[29, 289]`;生成小数秒用 |
| `seed` | int | 否 | `-1` | `[-1, 2^32-1]`,`-1` = 随机 |
| `camera_fixed` | bool | 否 | `false` | 参考图场景 / 2.0 系列不支持 |
| `watermark` | bool | 否 | `false` | 是否加平台水印 |

> **参数传入方式升级**:`resolution/ratio/duration/frames/seed/camera_fixed/watermark` 现在强烈推荐作为**顶层 JSON 字段**(强校验)。旧方式 `--rs 720p --ratio 16:9 --dur 5 --seed 11 --cf false --wm true` 追加在 prompt 尾部仍兼容(弱校验)。本项目统一走**新方式**。

#### 2.1.1 `content[]` 元素

**1) 文本**
```json
{ "type": "text", "text": "……图片1中……" }
```
- 提示词:中文 ≤500 字,英文 ≤1000 词;2.0 系列额外支持 日/印/西/葡语。

**2) 图片**
```json
{
  "type": "image_url",
  "image_url": { "url": "https://... 或 data:image/png;base64,... 或 asset://asset-xxxxx" },
  "role": "first_frame"   // 或 last_frame / reference_image
}
```

| 场景 | 图片数量 | `role` 取值 | 支持模型 |
|---|---|---|---|
| 图生视频-首帧 | 1 | `first_frame` 或不填 | 所有 i2v |
| 图生视频-首尾帧 | 2 | `first_frame` + `last_frame` | 2.0 / 2.0-fast / 1.5-pro / 1.0-pro / 1.0-lite-i2v |
| 参考图生视频 | 1~9(2.0)/1~4(1.0-lite-i2v) | 每张都是 `reference_image` | 2.0 / 2.0-fast / 1.0-lite-i2v |

> **三种场景互斥**(首帧、首尾帧、多模态参考),不可混用。

单张图片限制:格式 jpeg/png/webp/bmp/tiff/gif(1.5-pro 增 heic/heif);宽高比 (0.4, 2.5);边长 (300, 6000)px;大小 <30MB;请求体总大小 <64MB(大文件别用 base64)。

**3) 视频**(仅 2.0 / 2.0-fast)
```json
{
  "type": "video_url",
  "video_url": { "url": "https://... 或 asset://..." },
  "role": "reference_video"
}
```
- 格式 mp4/mov;时长单个 [2,15]s,最多 3 个,总时长 ≤15s;大小 ≤50MB;FPS [24,60];分辨率 480p/720p/1080p。
- **可信来源**:本账号近 30 天内由 2.0/2.0-fast 生成的含人脸视频,可直接二次创作。

**4) 音频**(仅 2.0 / 2.0-fast,且必须与至少 1 张图或 1 段视频同时传入)
```json
{
  "type": "audio_url",
  "audio_url": { "url": "https://... 或 data:audio/wav;base64,... 或 asset://..." },
  "role": "reference_audio"
}
```
- 格式 wav/mp3;单个时长 [2,15]s,最多 3 段,总时长 ≤15s;大小 ≤15MB。
- 输出始终是单声道,与输入声道数无关。

**5) 样片任务**(仅 1.5-pro)
```json
{ "type": "draft_task", "draft_task": { "id": "cgt-xxxxx" } }
```
基于之前 `draft=true` 生成的样片任务,自动复用其 model/text/image/generate_audio/seed/ratio/duration/camera_fixed,生成正式视频。

#### 2.1.2 响应

```json
{ "id": "cgt-20260421-xxxxx" }
```

#### 2.1.3 完整示例(复用人像库 asset + 多模态参考)

```bash
curl -X POST "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks" \
  -H "Authorization: Bearer $ARK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "doubao-seedance-2-0-260128",
    "content": [
      { "type": "text",
        "text": "图片1 里的女孩穿着图片2 的衣服,整理柜台物品,图片3 的男孩走上前打招呼,语气参考音频1 温柔口吻。" },
      { "type": "image_url", "role": "reference_image",
        "image_url": { "url": "asset://asset-20260224185115-hnjhb" } },
      { "type": "image_url", "role": "reference_image",
        "image_url": { "url": "asset://asset-20260224185115-8gghm" } },
      { "type": "image_url", "role": "reference_image",
        "image_url": { "url": "asset://asset-20260224185115-cjkwr" } },
      { "type": "audio_url", "role": "reference_audio",
        "audio_url": { "url": "asset://asset-20260224185115-dp9qm" } }
    ],
    "generate_audio": true,
    "resolution": "720p",
    "ratio": "16:9",
    "duration": 11,
    "watermark": false
  }'
```

### 2.2 查询任务 `GET /contents/generations/tasks/{id}`

仅保留最近 7 天 UTC 数据。

#### 响应字段(含所有字段)

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 任务 ID |
| `model` | string | 实际模型名-版本 |
| **`status`** | string | `queued` / `running` / `cancelled`(仅排队中可取消,取消 24h 后清理) / `succeeded` / `failed` / `expired` |
| `error` | object / null | 失败时返回 `{ code, message }` |
| `created_at` | int | Unix 秒 |
| `updated_at` | int | Unix 秒 |
| `content.video_url` | string | mp4,**24h 失效** |
| `content.last_frame_url` | string | 尾帧 PNG,**24h 失效**,需 `return_last_frame=true` |
| `seed` | int | 实际使用的种子 |
| `resolution` | string | 实际分辨率 |
| `ratio` | string | 实际宽高比(`adaptive` 时可查实际值) |
| `duration` / `frames` | int | **二者只返回一个**(看请求传的哪个) |
| `framespersecond` | int | 帧率 |
| `generate_audio` | bool | 2.0/2.0-fast/1.5-pro 返回 |
| `tools[].type` | string | 如 `web_search`(未使用不返回) |
| `safety_identifier` | string | 原样回传 |
| `draft` | bool | 1.5-pro 返回;表示本次输出是否 draft 视频 |
| `draft_task_id` | string | 基于 draft 生成正式视频时返回 |
| `service_tier` | string | 实际使用的服务等级 |
| `execution_expires_after` | int | 超时阈值秒数 |
| `usage.completion_tokens` | int | 计费 token(2.0 系列有最低用量) |
| `usage.total_tokens` | int | 等于 `completion_tokens`(输入 token 不计) |
| `usage.tool_usage.web_search` | int | 联网搜索实际次数(开启后返回) |

### 2.3 任务列表 `GET /contents/generations/tasks`

Query String:

| 参数 | 说明 |
|---|---|
| `page_num` | `[1, 500]` |
| `page_size` | `[1, 500]` |
| `filter.status` | `queued` / `running` / `cancelled` / `succeeded` / `failed` |
| `filter.task_ids` | 多个任务 ID 用 `&` 连接,如 `filter.task_ids=id1&filter.task_ids=id2` |
| `filter.model` | 推理接入点 ID,精确 |
| `filter.service_tier` | `default` / `flex` |

响应:`{ items: [ <与 §2.2 同结构> ], total: <int> }`。**本项目业务侧不依赖此接口做状态管理**,只当控制台/人工排查用。

### 2.4 取消或删除 `DELETE /contents/generations/tasks/{id}`

同一 URL,按当前状态行为不同(**只有以下状态可操作**):

| 当前状态 | 是否支持 | 操作含义 | 操作后状态 |
|---|---|---|---|
| `queued` | ✅ | 取消排队 | `cancelled` |
| `running` | ❌ | - | - |
| `succeeded` | ✅ | 删除记录 | - |
| `failed` | ✅ | 删除记录 | - |
| `cancelled` | ❌ | - | - |
| `expired` | ✅ | 删除记录 | - |

响应无 body。本项目用法:用户主动撤销 → 若 DB 中 `status=queued` 则调此接口,`running` 则只在 DB 置为"撤销中"并等待终态后再清理。

---

## 3. 图片生成 API

`POST https://ark.cn-beijing.volces.com/api/v3/images/generations`,Bearer 鉴权。

支持模型:
- `doubao-seedream-5.0-lite`(最新,支持流式、联网、组图、提示词优化)
- `doubao-seedream-4.5` / `doubao-seedream-4.0`
- `doubao-seedream-3.0-t2i`(仅文生图)

### 3.1 请求体

| 字段 | 类型 | 必填 | 默认 | 支持模型 / 说明 |
|---|---|---|---|---|
| `model` | string | 是 | - | Model ID 或 Endpoint ID |
| `prompt` | string | 是 | - | ≤300 汉字 / ≤600 英文词 |
| `image` | string / array | 否 | - | 3.0-t2i 不支持;5.0-lite/4.5/4.0 支持单/多图(2~14 张);URL 或 `data:image/xxx;base64,...` |
| `size` | string | 否 | `2048x2048`(5.0/4.5/4.0) / `1024x1024`(3.0-t2i) | 两种方式(不可混用):① 档位 `1K`/`2K`/`3K`/`4K`(5.0-lite 仅 2K/3K;4.5 仅 2K/4K;4.0 全部;3.0-t2i 不支持档位);② `<宽>x<高>` 像素值,宽高比 [1/16, 16];总像素按模型不同([921600, 16777216] 等) |
| `seed` | int | 否 | `-1` | 仅 3.0-t2i,`[-1, 2147483647]` |
| `sequential_image_generation` | string | 否 | `disabled` | 仅 5.0-lite/4.5/4.0;`auto`=生成组图;`disabled`=单图 |
| `sequential_image_generation_options.max_images` | int | 否 | `15` | 上限 15,且"参考图数 + 输出图数 ≤ 15" |
| `tools` | object[] | 否 | - | 仅 5.0-lite;`[{"type":"web_search"}]` |
| `stream` | bool | 否 | `false` | 仅 5.0-lite/4.5/4.0;流式逐张返回 |
| `guidance_scale` | float | 否 | `2.5`(3.0-t2i) | **仅 3.0-t2i**;范围 `[1, 10]` |
| `output_format` | string | 否 | `jpeg` | 仅 5.0-lite;`png`/`jpeg` |
| `response_format` | string | 否 | `url` | `url`(**24h 失效**)/ `b64_json` |
| `watermark` | bool | 否 | **`true`** | ⚠️ **默认加水印**,要关必须显式 `false` |
| `optimize_prompt_options.mode` | string | 否 | `standard` | 仅 5.0-lite/4.5/4.0;`standard`/`fast`(5.0-lite/4.5 不支持 fast) |

### 3.2 响应(非流式)

```json
{
  "model": "doubao-seedream-4-0-250828",
  "created": 1718049470,
  "data": [
    { "url": "https://...xxx.jpg", "size": "2048x2048" }
  ],
  "tools": [{ "type": "web_search" }],
  "usage": {
    "generated_images": 1,
    "output_tokens": 16384,
    "total_tokens": 16384,
    "tool_usage": { "web_search": 0 }
  }
}
```

- `data[].url`:`response_format=url` 时返回
- `data[].b64_json`:`response_format=b64_json` 时返回
- `data[].error`(组图场景下某张失败):`{ code, message }`,继续生成下一张(审核失败时)
- `usage.output_tokens`:`sum(宽*高)/256` 向下取整
- 流式响应见 https://www.volcengine.com/docs/82379/1824137

### 3.3 本项目建议

- 封面图/分镜:`doubao-seedream-4-0-250828`,`size=1152x864`,`watermark=false`,`response_format=url` → 立即下载到自家 OSS
- 短剧多分镜:用 `sequential_image_generation=auto` 一次出一组 6~10 张保持风格一致

---

## 4. 对话 Chat API

`POST https://ark.cn-beijing.volces.com/api/v3/chat/completions`,OpenAI 兼容。

### 4.1 请求体(全字段)

#### 通用

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `model` | string | - | Model ID 或 Endpoint ID |
| `messages` | object[] | - | 见 §4.1.1 |
| `stream` | bool | `false` | `true` 时返回 SSE,结束于 `data: [DONE]` |
| `stream_options.include_usage` | bool | `false` | 在 `[DONE]` 前多发一个 chunk,含最终 `usage`,`choices=[]` |
| `stream_options.chunk_include_usage` | bool | `false` | 每个 chunk 都带到该 chunk 为止的累计 usage |
| `max_tokens` | int | `4096` | 输出长度上限(回答部分) |
| `max_completion_tokens` | int | - | `[1, 65536]`;设了之后 `max_tokens` 失效,上限包括思维链 |
| `service_tier` | string | `auto` | `fast`(低延迟包优先)/ `auto`(TPM 保障包优先)/ `default`(只用常规) |
| `stop` | string / string[] | - | ≤4 个,深度思考模型不支持 |
| `temperature` | float | `1` | `[0, 2]`;`doubao-seed-2-0-*` 固定 1 |
| `top_p` | float | `0.7` | `(0, 1]`;`doubao-seed-2-0-*` 固定 0.95 |
| `frequency_penalty` | float | `0` | `[-2, 2]`;`doubao-seed-1.8/2.0` 不支持 |
| `presence_penalty` | float | `0` | `[-2, 2]`;同上 |
| `logprobs` | bool | `false` | 深度思考模型不支持 |
| `top_logprobs` | int | `0` | `[0, 20]`,需 `logprobs=true` |
| `logit_bias` | map | - | `{ "<token_id>": -100..100 }` |
| `thinking.type` | string | 模型默认 | `enabled` / `disabled` / `auto`(部分模型默认 enabled) |
| `reasoning_effort` | string | `medium` | `minimal` / `low` / `medium` / `high` |
| `response_format` | object | `{"type":"text"}` | `text` / `json_object` / `json_schema`(beta) |
| `tools` | object[] | - | `[{ "type":"function", "function":{ "name","description","parameters":<JSONSchema> } }]` |
| `parallel_tool_calls` | bool | `true` | 允许并行调多工具(1.6+ 生效) |
| `tool_choice` | string / object | `auto` | `none` / `auto` / `required` / `{"type":"function","function":{"name":"..."}}` |

#### 4.1.1 `messages` 结构

- **system**:`{ "role":"system", "content": <string 或 object[]> }`
- **user**:`{ "role":"user", "content": <string 或 object[]> }`
- **assistant**:`{ "role":"assistant", "content"?: string, "reasoning_content"?: string, "tool_calls"?: [{id,type:"function",function:{name,arguments}}] }`
- **tool**:`{ "role":"tool", "tool_call_id":"call_xxx", "content": string | array }`

多模态 `content[]` 元素:

```json
// 文本
{ "type":"text", "text":"..." }

// 图片
{ "type":"image_url",
  "image_url":{
    "url":"https://... 或 data:image/png;base64,...",
    "detail":"low" | "high" | "xhigh",
    "image_pixel_limit":{ "min_pixels":1764, "max_pixels":9031680 }
  } }

// 视频
{ "type":"video_url",
  "video_url":{ "url":"...", "fps":1.0 } }
```

- `detail`:不同模型默认不同,详见模型卡
- `image_pixel_limit.max_pixels`:1.8 之前 ≤4014080;1.8/2.0 ≤9031680
- `video_url.fps`:`[0.2, 5]`,默认 1
- 视频理解**不含音频**

#### 4.1.2 JSON Schema 结构化输出

```json
"response_format": {
  "type": "json_schema",
  "json_schema": {
    "name": "script_output",
    "description": "漫画剧本分场结构",
    "schema": { "type":"object", "properties":{...}, "required":[...] },
    "strict": true
  }
}
```

### 4.2 响应(非流式)

```json
{
  "id": "chatcmpl-xxxxx",
  "object": "chat.completion",
  "created": 1718049470,
  "model": "doubao-seed-1-6-251015",
  "service_tier": "scale",
  "choices": [{
    "index": 0,
    "finish_reason": "stop",
    "message": {
      "role": "assistant",
      "content": "……",
      "reasoning_content": null,
      "tool_calls": null
    },
    "logprobs": null,
    "moderation_hit_type": null
  }],
  "usage": {
    "prompt_tokens": 128,
    "prompt_tokens_details": { "cached_tokens": 0 },
    "completion_tokens": 256,
    "completion_tokens_details": { "reasoning_tokens": 0 },
    "total_tokens": 384
  }
}
```

- `finish_reason`:`stop` / `length`(`max_tokens` / `max_completion_tokens` / `context_window` 触顶)/ `content_filter` / `tool_calls`
- `service_tier` 返回:`scale`(TPM 保障)/ `default` / `fast`
- `message.reasoning_content`:仅 `doubao-seed-1.8 / deepseek-v3.2 / doubao-seed-2.0` 返回思维链
- `moderation_hit_type`:`severe_violation` / `violence`,仅视觉理解模型 + 接入点配 `ModerationStrategy=Basic` 时返回

### 4.3 流式返回

`text/event-stream`,每个 chunk:

```
data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":...,
       "model":"...","service_tier":"...","choices":[
         {"index":0,"delta":{"role":"assistant","content":"你"},"finish_reason":null,"logprobs":null}
       ]}
```

- `object` 固定 `chat.completion.chunk`
- 首 chunk 的 `delta.role`,后续 `delta.content`
- 工具调用:`delta.tool_calls[].function.arguments` 分片拼接
- 默认 `usage=null`;请求带 `stream_options.include_usage=true` 才在 `[DONE]` 前返回一个独立 usage chunk
- 终止:`data: [DONE]`(非 JSON)

### 4.4 本项目使用(OpenAI SDK)

```python
from openai import OpenAI
client = OpenAI(
    api_key=os.environ["ARK_API_KEY"],
    base_url="https://ark.cn-beijing.volces.com/api/v3",
)
resp = client.chat.completions.create(
    model="doubao-seed-1-6-251015",
    messages=[
        {"role": "system", "content": "你是漫画剧本分场助手,输出 JSON。"},
        {"role": "user", "content": "拆成 6 个分镜..."},
    ],
    response_format={"type": "json_object"},
    temperature=0.7,
)
print(resp.choices[0].message.content)
```

---

## 5. 错误处理与重试策略(本项目约定)

**按错误类别分层**,不一刀切:

| 类别 | 示例 HTTP / code | 处理 |
|---|---|---|
| 鉴权 | `401` / `AuthenticationError` / `InvalidApiKey` | **不重试**,写 DB 告警 |
| 权限 | `403` / `AccessDenied` | **不重试**,写 DB 告警 |
| 参数 | `400` / `InvalidParameter` / `ModelNotFound` | **不重试**,直接失败,回写 `remix_jobs.error` |
| 限流 | `429` / `RateLimitExceeded` | **指数退避**,尊重 `Retry-After`,上限 3 次 |
| 服务端 | `5xx` / `InternalServiceError` | 指数退避 base 2s,上限 3 次 |
| 内容审核 | `OutputVideoSensitiveContentDetected` / `content_filter` / 图片生成 `data[].error` | **不重试**,用户侧脱敏话术 |
| 网络超时 | Connection/Timeout | 重试,上限 2 次 |
| 任务终态 `failed` | `status=failed` + `error.code` | 按 `error.code` 再匹配以上类别 |
| 任务 `expired` | `status=expired` | 不重试(超时阈值是请求时设的),提示用户重建任务 |
| 人像库 `Status=Failed` | `GetAsset` 返回 Failed | 不重试,提示用户换图 |

---

## 6. 本项目对接落点

| 场景 | 调用 | 落库字段(`remix_jobs` / 其他) |
|---|---|---|
| 剧本改写、对话式编辑 | Chat | `remix_jobs.scriptwriting_*` |
| 素材理解(视觉模型) | Chat 多模态 | `remix_jobs.material_matching_*` |
| 分镜/封面图 | Image(`doubao-seedream-4-0`) | `remix_assets.image_url`(自家 OSS 地址) |
| 角色参考形象入库 | AssetGroup + Asset(轮询 Active) | `characters.avatar_group_id` / `characters.avatar_asset_id` |
| 视频渲染 | Video 创建 + 轮询 | `remix_jobs.task_id` / `remix_jobs.video_url`(自家 OSS) |
| 用户撤销 | Video `DELETE`(仅 queued) | `remix_jobs.status=cancelled` |

> **硬规则**:视频/图片/人像库 URL 全部有过期时间;任务一进入 `succeeded` 立刻拉流存到本项目 TOS/S3,业务表只存自家 OSS URL。视频流水线建议启用 TOS 数据订阅自动转存。

---

## 7. 文档与参考

本项目 `docs/huoshan_api/` 下为火山官方原文备份:
- `创建视频生成任务 API.md`
- `查询视频生成任务 API.md`
- `查询视频生成任务列表.md`
- `取消或删除视频生成任务.md`
- `图片生成 API.md`
- `对话(Chat) API.md`
- `私域虚拟人像素材资产库使用指南.md` + `人像库 demo/*.py`(AK/SK 签名参考实现)

官方在线文档(随时可能更新):
- [创建视频生成任务](https://www.volcengine.com/docs/82379/1520757?lang=zh)
- [查询视频生成任务](https://www.volcengine.com/docs/82379/1521309?lang=zh)
- [查询视频生成任务列表](https://www.volcengine.com/docs/82379/1521675?lang=zh)
- [取消或删除视频生成任务](https://www.volcengine.com/docs/82379/1521720?lang=zh)
- [图片生成 API](https://www.volcengine.com/docs/82379/1541523?lang=zh)
- [对话(Chat) API](https://www.volcengine.com/docs/82379/1494384?lang=zh)
- [私域虚拟人像素材资产库使用指南](https://www.volcengine.com/docs/82379/2333565?lang=zh)
- [私域虚拟人像库 API 参考](https://www.volcengine.com/docs/82379/2333601?lang=zh)
- [Seedance 2.0 教程](https://www.volcengine.com/docs/82379/2291680?lang=zh)
- [Base URL 及鉴权](https://www.volcengine.com/docs/82379/1298459?lang=zh)
- [AK/SK 管理(IAM)](https://www.volcengine.com/docs/6257/64983?lang=zh)
- [错误码](https://www.volcengine.com/docs/82379/1299023?lang=zh)
