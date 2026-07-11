"""主动识图插件 — 关闭自动被动识图，为 Bot 提供主动识图工具。"""

from __future__ import annotations

import base64
from collections import deque
from typing import Any

from maibot_sdk import Field, HookHandler, MaiBotPlugin, PluginConfigBase, Tool
from maibot_sdk.types import HookMode, HookOrder, ToolParameterInfo, ToolParamType


class PluginSectionConfig(PluginConfigBase):
    __ui_label__ = "插件"
    __ui_icon__ = "package"
    __ui_order__ = 0

    enabled: bool = Field(default=False, description="是否启用插件")
    config_version: str = Field(default="1.0.0", description="配置版本")


class CacheConfig(PluginConfigBase):
    __ui_label__ = "缓存"
    __ui_icon__ = "database"
    __ui_order__ = 1

    max_images: int = Field(default=200, description="最大缓存的图片数量")


class ActiveImageRecognitionConfig(PluginConfigBase):
    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)


class ActiveImageRecognitionPlugin(MaiBotPlugin):
    """主动识图插件 — 关闭被动识图并暴露主动识图工具。"""

    config_model = ActiveImageRecognitionConfig

    def __init__(self) -> None:
        super().__init__()
        self._session_counters: dict[str, int] = {}
        self._image_cache: dict[tuple[str, int], dict[str, Any]] = {}
        self._cache_keys: deque[tuple[str, int]] = deque()

    async def on_load(self) -> None:
        self._session_counters.clear()
        self._image_cache.clear()
        self._cache_keys.clear()
        self.ctx.logger.info("主动识图插件已加载")

    async def on_unload(self) -> None:
        self._session_counters.clear()
        self._image_cache.clear()
        self._cache_keys.clear()
        self.ctx.logger.info("主动识图插件已卸载")

    async def on_config_update(self, scope: str, config_data: dict[str, Any], version: str) -> None:
        pass

    def _trim_cache(self) -> None:
        max_size = max(0, self.config.cache.max_images)
        if len(self._image_cache) <= max_size:
            return
        target = max(1, max_size * 80 // 100)
        while len(self._image_cache) > target and self._cache_keys:
            key = self._cache_keys.popleft()
            self._image_cache.pop(key, None)

    def _get_image_format(self, raw_bytes: bytes) -> str:
        if raw_bytes[:2] == b"\xff\xd8":
            return "jpeg"
        if raw_bytes[:4] == b"\x89PNG":
            return "png"
        if raw_bytes[:3] in (b"GIF",):
            return "gif"
        if raw_bytes[:4] == b"RIFF" and raw_bytes[8:12] == b"WEBP":
            return "webp"
        return "png"

    def _process_components(
        self,
        components: list[dict[str, Any]],
        session_id: str,
    ) -> None:
        for comp in components:
            comp_type = comp.get("type", "")
            if comp_type == "image":
                self._process_single_image(comp, session_id)
            elif comp_type == "forward":
                self._process_forward(comp, session_id)

    def _process_single_image(
        self,
        comp: dict[str, Any],
        session_id: str,
    ) -> None:
        counter = self._session_counters.get(session_id, 0) + 1
        self._session_counters[session_id] = counter

        key = (session_id, counter)
        raw_b64 = comp.get("binary_data_base64", "")
        entry: dict[str, Any] = {"hash": comp.get("hash", "")}

        if raw_b64:
            try:
                raw_bytes = base64.b64decode(raw_b64)
                entry["bytes"] = raw_bytes
                entry["format"] = self._get_image_format(raw_bytes)
            except Exception as exc:
                self.ctx.logger.warning("图片 base64 解码失败: %s", exc)

        self._image_cache[key] = entry
        self._cache_keys.append(key)
        self._trim_cache()

        comp["data"] = f"[图片 #{counter}]"
        comp.pop("binary_data_base64", None)

    def _process_forward(
        self,
        comp: dict[str, Any],
        session_id: str,
    ) -> None:
        forward_data = comp.get("data")
        if not isinstance(forward_data, list):
            return
        for sub_msg in forward_data:
            if not isinstance(sub_msg, dict):
                continue
            sub_content = sub_msg.get("content")
            if isinstance(sub_content, list):
                self._process_components(sub_content, session_id)

    @HookHandler(
        "chat.receive.before_process",
        name="strip_image_for_active_recognition",
        description="拦截图片并替换为索引占位符，关闭被动识图",
        mode=HookMode.BLOCKING,
        order=HookOrder.EARLY,
    )
    async def handle_before_process(self, message: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        del kwargs

        if not isinstance(message, dict):
            return {"action": "continue"}

        session_id = message.get("session_id", "")
        if not session_id:
            return {"action": "continue"}

        raw_message = message.get("raw_message")
        if not isinstance(raw_message, list):
            return {"action": "continue"}

        self._process_components(raw_message, session_id)

        return {
            "action": "continue",
            "modified_kwargs": {"message": message},
        }

    @Tool(
        "recognize_image",
        description=(
            "当你需要查看某张图片的内容时使用此工具。"
            "查看消息历史中的图片，通过图片编号指定要识别的图片。"
            "调用后返回图片的详细描述。"
        ),
        core_tool=True,
        parameters=[
            ToolParameterInfo(
                name="image_number",
                param_type=ToolParamType.INTEGER,
                description="图片编号，对应消息历史中 [图片 #N] 的 N",
                required=True,
            ),
        ],
    )
    async def handle_recognize_image(self, image_number: int = 0, **kwargs: Any) -> dict[str, Any]:
        stream_id = kwargs.get("stream_id", "")

        if image_number < 1:
            return {"content": "图片编号必须大于 0"}

        key = (stream_id, image_number)
        entry = self._image_cache.get(key)

        if entry is None:
            return {"content": f"未找到图片 #{image_number}，该图片可能已过期或不存在"}

        raw_bytes = entry.get("bytes")
        if not raw_bytes:
            return {"content": f"图片 #{image_number} 的原始数据不可用，无法识别"}

        img_format = entry.get("format", "png")
        b64_data = base64.b64encode(raw_bytes).decode("utf-8")

        try:
            result = await self.ctx.llm.generate(
                prompt=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "请用中文详细描述这张图片的内容。如果有文字，请把文字概括出来。注意其主题和直观感受，输出一段平实文本，最多150字。",
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/{img_format};base64,{b64_data}"},
                            },
                        ],
                    },
                ],
            )
        except Exception as e:
            return {"content": f"识别图片 #{image_number} 时出错：{e}"}

        if not isinstance(result, dict):
            return {"content": f"识别图片 #{image_number} 失败：模型返回格式异常"}

        description = result.get("response") or result.get("content") or ""
        if not description:
            return {"content": f"图片 #{image_number} 识别结果为空"}

        return {
            "content": f"图片 #{image_number} 的内容：{description}",
            "content_items": [
                {
                    "content_type": "image",
                    "data": b64_data,
                    "mime_type": f"image/{img_format}",
                    "description": description,
                },
            ],
        }


def create_plugin() -> ActiveImageRecognitionPlugin:
    return ActiveImageRecognitionPlugin()
