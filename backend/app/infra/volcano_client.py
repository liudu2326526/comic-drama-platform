import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.config import get_settings
from app.infra.volcano_errors import (
    VolcanoAuthError,
    VolcanoError,
    VolcanoRateLimitError,
    VolcanoServerError,
    VolcanoTimeoutError,
    classify_http,
    classify_exception,
)

logger = logging.getLogger(__name__)


class VolcanoClient(ABC):
    @abstractmethod
    async def chat_completions(self, model: str, messages: list[dict], **kwargs) -> Any:
        pass

    @abstractmethod
    async def image_generations(
        self,
        model: str,
        prompt: str,
        *,
        references: list[str] | None = None,
        n: int = 1,
        size: str | None = None,
        **kwargs: Any,
    ) -> Any:
        pass

    @abstractmethod
    async def video_generations_create(self, **kwargs: Any) -> Any:
        pass

    @abstractmethod
    async def video_generations_get(self, task_id: str) -> Any:
        pass

    @abstractmethod
    async def video_generations_delete(self, task_id: str) -> Any:
        pass


class _ChatResponse:
    """兼容 mock 和 openai SDK 的响应结构。"""

    class Choice:
        class Message:
            def __init__(self, content: str):
                self.content = content
                self.role = "assistant"

        def __init__(self, content: str, finish_reason: str):
            self.message = self.Message(content)
            self.finish_reason = finish_reason

    def __init__(self, content: str, finish_reason: str = "stop"):
        self.choices = [self.Choice(content, finish_reason)]

    @classmethod
    def from_dict(cls, data: dict) -> "_ChatResponse":
        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        return cls(
            content=msg.get("content", ""),
            finish_reason=choice.get("finish_reason", "stop"),
        )


class MockVolcanoClient(VolcanoClient):
    """
    M2 使用的 Mock 客户端。不真正调 API,按 M2 任务需求返回固定格式的假数据。
    """

    async def chat_completions(self, model: str, messages: list[dict], **kwargs) -> Any:
        user_msg = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        logger.info(f"Mock Volcano Chat: model={model}, user_msg={user_msg[:50]}")

        # 0.1 镜头草稿：参考图自动选择
        if "请先为当前镜头选择参考图" in user_msg:
            content = {
                "reference_ids": [],
                "selection_notes": {
                    "scene": "mock 环境使用默认候选选择",
                    "characters": ["mock 环境使用默认候选选择"],
                },
            }
            resp_str = json.dumps(content, ensure_ascii=False)
            print(f"\n[AI Chat Output] Model: {model}\nContent: {resp_str}\n")
            return _ChatResponse(resp_str)

        # 0.2 镜头草稿：提示词生成
        if "请基于当前镜头与已选参考图" in user_msg:
            content = {
                "prompt": "mock 镜头草稿：根据已选场景与人物参考图生成稳定构图，保持角色身份一致，镜头缓慢推进。",
                "optimizer_notes": {
                    "issues": [],
                    "principles": ["mock two-step draft"],
                    "assumptions": ["使用默认参考图候选"],
                },
            }
            resp_str = json.dumps(content, ensure_ascii=False)
            print(f"\n[AI Chat Output] Model: {model}\nContent: {resp_str}\n")
            return _ChatResponse(resp_str)

        # 1. 小说解析任务 (parse_novel)
        if "解析" in user_msg and "JSON" in user_msg:
            content = {
                "summary": "这是一个关于勇气的虚构故事。",
                "parsed_stats": ["角色: 3", "场景: 2", "预计时长: 60s"],
                "overview": "故事发生在遥远的未来,人类与 AI 共存...",
                "suggested_shots": 12,
                "genre": "科幻冒险",
            }
            resp_str = json.dumps(content)
            print(f"\n[AI Chat Output] Model: {model}\nContent: {resp_str}\n")
            return _ChatResponse(resp_str)

        # 1.5 角色提取任务 (gen_character_asset)
        if "角色" in user_msg and "提取" in user_msg:
            content = {
                "characters": [
                    {
                        "name": "秦昭",
                        "role_type": "protagonist",
                        "is_humanoid": True,
                        "summary": "少年天子",
                        "description": "十五六岁清瘦少年男性,眉眼稚气但神情倔强,黑色束发,深青窄袖常服外罩短披风,银灰腰带,黑布靴,袖口有细金线作为唯一辨识点。"
                    },
                    {
                        "name": "江离",
                        "role_type": "supporting",
                        "is_humanoid": True,
                        "summary": "摄政王",
                        "description": "三十岁上下高挑男性,肩背挺直,冷峻长脸,乌发整齐束冠,玄黑长袍叠深紫外衫,玉白腰佩,硬底长靴,左肩暗纹披帛作为唯一辨识点。"
                    }
                ]
            }
            resp_str = json.dumps(content)
            print(f"\n[AI Chat Output] Model: {model}\nContent: {resp_str}\n")
            return _ChatResponse(resp_str)

        # 1.6 场景提取任务 (gen_scene_asset)
        if "场景" in user_msg and "提取" in user_msg:
            content = {
                "scenes": [
                    {
                        "name": "长安殿",
                        "theme": "palace",
                        "summary": "金碧辉煌的大殿",
                        "description": "权力交锋的中心。"
                    },
                    {
                        "name": "御花园",
                        "theme": "palace",
                        "summary": "幽静的花园",
                        "description": "偶遇与密谈之所。"
                    }
                ]
            }
            resp_str = json.dumps(content)
            print(f"\n[AI Chat Output] Model: {model}\nContent: {resp_str}\n")
            return _ChatResponse(resp_str)

        # 2.1 分镜片段扩写任务 (gen_storyboard V2)
        elif "具体分镜" in user_msg and "beats" in user_msg:
            match = re.search(r'"idx":\s*(\d+)', user_msg)
            idx = int(match.group(1)) if match else 1
            content = {
                "idx": idx,
                "title": f"分镜 {idx}",
                "description": f"这是第 {idx} 个 8 秒视频片段，按原文展开关键动作和情绪变化。",
                "detail": (
                    "8秒，9:16竖屏。0-3s：远景固定机位展示场景氛围；"
                    "3-6s：中景缓慢推进至角色动作；6-8s：特写捕捉情绪反应，光影压抑。"
                ),
                "duration_sec": 8,
                "tags": [f"分镜{idx}", "测试场景", "压抑"],
                "beats": [
                    {
                        "time": "0-3s",
                        "shot_type": "远景",
                        "camera_movement": "固定机位",
                        "action": "展示场景氛围",
                        "visual": "冷色光影",
                    },
                    {
                        "time": "3-6s",
                        "shot_type": "中景",
                        "camera_movement": "缓慢推进",
                        "action": "角色完成关键动作",
                        "visual": "雨雾弥散",
                    },
                    {
                        "time": "6-8s",
                        "shot_type": "特写",
                        "camera_movement": "固定机位",
                        "action": "捕捉情绪反应",
                        "visual": "压抑暗调",
                    },
                ],
            }
            resp_str = json.dumps(content, ensure_ascii=False)
            print(f"\n[AI Chat Output] Model: {model}\nContent: {resp_str}\n")
            return _ChatResponse(resp_str)

        # 2.2 分镜片段规划任务 (gen_storyboard V2)
        elif "视频片段级分镜" in user_msg:
            storyboards = []
            for i in range(1, 11):  # 固定返回 10 条
                storyboards.append(
                    {
                        "idx": i,
                        "title": f"分镜 {i}",
                        "description": f"这是第 {i} 个视频片段的剧情描述内容。",
                        "duration_sec": 8,
                        "source_query": f"勇敢 小骑士 分镜 {i}",
                        "key_characters": ["小骑士"],
                        "key_scene": "测试场景",
                        "narrative_purpose": "推动剧情",
                        "tags": [f"分镜{i}", "小骑士", "测试场景"],
                    }
                )
            resp_str = json.dumps(storyboards, ensure_ascii=False)
            print(f"\n[AI Chat Output] Model: {model}\nContent: {resp_str}\n")
            return _ChatResponse(resp_str)

        # 2.3 旧分镜生成任务兼容
        elif "分镜" in user_msg:
            storyboards = []
            for i in range(1, 11):
                storyboards.append(
                    {
                        "idx": i,
                        "title": f"分镜 {i}",
                        "description": f"这是第 {i} 个镜头的详细描述内容。",
                        "detail": f"镜头 {i} 的视觉细节提示词",
                        "duration_sec": 5.0,
                    }
                )
            resp_str = json.dumps(storyboards, ensure_ascii=False)
            print(f"\n[AI Chat Output] Model: {model}\nContent: {resp_str}\n")
            return _ChatResponse(resp_str)

    async def image_generations(
        self,
        model: str,
        prompt: str,
        *,
        references: list[str] | None = None,
        n: int = 1,
        size: str | None = None,
        **kwargs: Any,
    ) -> Any:
        logger.info(f"Mock Volcano Image: model={model}, prompt={prompt[:50]}, refs={len(references or [])}")
        img_url = "https://placehold.co/1024x1024?text=Mock+Image"
        print(f"\n[AI Image Output] Model: {model}\nURL: {img_url}\n")
        return {"data": [{"url": img_url}]}

    async def video_generations_create(self, **kwargs: Any) -> Any:
        logger.info("Mock Volcano Video Create")
        return {"id": "mock-video-task"}

    async def video_generations_get(self, task_id: str) -> Any:
        logger.info("Mock Volcano Video Get")
        return {
            "id": task_id,
            "status": "succeeded",
            "content": {
                "video_url": "https://placehold.co/720x1280.mp4",
                "last_frame_url": "https://placehold.co/720x1280.png?text=Mock+Last+Frame",
            },
        }

    async def video_generations_delete(self, task_id: str) -> Any:
        logger.info("Mock Volcano Video Delete")
        return {"id": task_id, "status": "cancelled"}


class RealVolcanoClient(VolcanoClient):
    """
    M3a 真正实现的客户端。使用 httpx 直连,支持重试与错误分类。
    """

    def __init__(self) -> None:
        s = get_settings()
        if not s.ark_api_key:
            raise VolcanoAuthError("ark_api_key 未配置")
        self._client = httpx.AsyncClient(
            base_url=s.ark_base_url,
            headers={
                "Authorization": f"Bearer {s.ark_api_key}",
                "Content-Type": "application/json",
            },
            timeout=s.ai_request_timeout_sec,
            trust_env=False,
        )
        self._settings = s

    async def _request_with_retry(self, method: str, path: str, json_body: dict | None = None) -> dict:
        last_exc: Exception | None = None
        for attempt in range(self._settings.ai_retry_max):
            try:
                logger.info(f"Real Volcano Request: {method} {path} (attempt {attempt+1})")
                resp = await self._client.request(method, path, json=json_body)
                logger.info(f"Real Volcano Response: {resp.status_code}")
                classify_http(resp)
                return resp.json()
            except httpx.HTTPError as e:
                volcano_err = classify_exception(e)
                if isinstance(volcano_err, (VolcanoServerError, VolcanoTimeoutError)):
                    last_exc = volcano_err
                    await asyncio.sleep(self._settings.ai_retry_base_sec * (4**attempt))
                    continue
                raise volcano_err
            except VolcanoRateLimitError as e:
                last_exc = e
                delay = e.retry_after or (self._settings.ai_retry_base_sec * (4**attempt))
                await asyncio.sleep(delay)
            except (VolcanoServerError, VolcanoTimeoutError) as e:
                last_exc = e
                await asyncio.sleep(self._settings.ai_retry_base_sec * (4**attempt))
            except VolcanoError:
                raise  # 不可重试的错误(Auth/Param/ContentFilter)直接抛出
        raise last_exc or VolcanoServerError("exhausted retries")

    async def chat_completions(self, model: str, messages: list[dict], **kwargs: Any) -> Any:
        body = {"model": model, "messages": messages, **kwargs}
        resp_json = await self._request_with_retry("POST", "/chat/completions", body)
        resp = _ChatResponse.from_dict(resp_json)
        print(f"\n[AI Chat Output] Model: {model}\nContent: {resp.choices[0].message.content}\n")
        return resp

    async def image_generations(
        self,
        model: str,
        prompt: str,
        *,
        references: list[str] | None = None,
        n: int = 1,
        size: str | None = None,
        **kwargs: Any,
    ) -> Any:
        if references:
            body = {
                "model": model,
                "prompt": prompt,
                "image": references,
                "response_format": "url",
                "watermark": False,
                **kwargs,
            }
        else:
            body = {
                "model": model,
                "prompt": prompt,
                "response_format": "url",
                "watermark": False,
                **kwargs,
            }

        if size:
            body["size"] = size
        if n != 1:
            body["n"] = n

        resp_json = await self._request_with_retry("POST", "/images/generations", body)
        urls = [item.get("url") for item in resp_json.get("data", [])]
        print(f"\n[AI Image Output] Model: {model}\nURLs: {urls}\n")
        return resp_json

    async def video_generations_create(
        self,
        *,
        model: str,
        prompt: str,
        duration: int | None,
        resolution: str,
        ratio: str,
        references: list[str] | None = None,
        image_inputs: list[dict[str, str]] | None = None,
        generate_audio: bool = False,
        reference_audio_url: str | None = None,
        watermark: bool = False,
        return_last_frame: bool = True,
        execution_expires_after: int = 3600,
    ) -> dict:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for item in image_inputs or []:
            content.append({
                "type": "image_url",
                "role": item["role"],
                "image_url": {"url": item["url"]},
            })
        for url in references or []:
            content.append({"type": "image_url", "role": "reference_image", "image_url": {"url": url}})
        if reference_audio_url:
            content.append({
                "type": "audio_url",
                "role": "reference_audio",
                "audio_url": {"url": reference_audio_url},
            })
        body = {
            "model": model,
            "content": content,
            "resolution": resolution,
            "ratio": ratio,
            "generate_audio": generate_audio,
            "watermark": watermark,
            "return_last_frame": return_last_frame,
            "execution_expires_after": execution_expires_after,
        }
        if duration is not None:
            body["duration"] = duration
        return await self._request_with_retry("POST", "/contents/generations/tasks", body)

    async def video_generations_get(self, task_id: str) -> dict:
        return await self._request_with_retry("GET", f"/contents/generations/tasks/{task_id}", None)

    async def video_generations_delete(self, task_id: str) -> dict:
        return await self._request_with_retry("DELETE", f"/contents/generations/tasks/{task_id}", None)


def get_volcano_client() -> VolcanoClient:
    settings = get_settings()
    if settings.ai_provider_mode == "mock":
        return MockVolcanoClient()
    return RealVolcanoClient()
