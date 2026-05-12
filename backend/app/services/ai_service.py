from __future__ import annotations

import json
import re
from typing import Any, Protocol

import requests

from backend.app.models import ModelConfig


class TextAiClient(Protocol):
    def rewrite_note(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        title: str,
        body: str,
        instruction: str,
    ) -> str:
        ...

    def generate_note(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        topic: str,
        reference: str,
        instruction: str,
    ) -> dict[str, str]:
        ...

    def generate_titles(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        title: str,
        body: str,
        count: int,
    ) -> list[str]:
        ...

    def generate_tags(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        title: str,
        body: str,
        count: int,
    ) -> list[str]:
        ...

    def polish_text(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        text: str,
        instruction: str,
    ) -> str:
        ...

    def generate_agent_drafts(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        messages: list[dict],
        n: int,
        temperature: float,
        top_p: float,
        output_requirements: str | None,
        reference_image_urls: list[str],
    ) -> dict:
        ...


class ImageAiClient(Protocol):
    def generate_cover(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        prompt: str,
        size: str,
        style: str,
    ) -> dict[str, Any]:
        ...

    def generate_image(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        prompt: str,
        reference_images: list[str] | None = None,
    ) -> dict[str, Any]:
        ...

    def describe_image(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        image_url: str,
        instruction: str,
    ) -> str:
        ...


class OpenAICompatibleTextClient:
    def _complete(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
    ) -> str:
        if not model_config.base_url:
            raise ValueError("Text model base_url is required")
        if not model_config.model_name:
            raise ValueError("Text model_name is required")
        if not api_key:
            raise ValueError("Text model api_key is required")

        endpoint = f"{model_config.base_url.rstrip('/')}/chat/completions"
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model_config.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("AI response missing choices[0].message.content") from exc
        if not isinstance(content, str) or not content.strip():
            raise ValueError("AI response content is empty")
        return content.strip()

    def rewrite_note(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        title: str,
        body: str,
        instruction: str,
    ) -> str:
        return self._complete(
            model_config=model_config,
            api_key=api_key,
            system_prompt="你是小红书内容运营编辑，负责在保留事实的前提下改写成自然、可发布的种草笔记。",
            user_prompt=(
                f"改写要求：{instruction or '提升表达、增强小红书语感'}\n\n"
                f"标题：{title}\n\n正文：\n{body}"
            ),
        )

    def generate_note(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        topic: str,
        reference: str,
        instruction: str,
    ) -> dict[str, str]:
        content = self._complete(
            model_config=model_config,
            api_key=api_key,
            system_prompt="你是小红书内容策划，输出可发布的标题和正文。",
            user_prompt=(
                "请生成一篇小红书笔记，格式必须是：\n标题：...\n正文：...\n\n"
                f"选题：{topic}\n参考材料：{reference or '无'}\n要求：{instruction or '自然、有信息密度'}"
            ),
        )
        title = topic
        body = content
        for line in content.splitlines():
            if line.startswith("标题："):
                title = line.replace("标题：", "", 1).strip() or title
                break
        if "正文：" in content:
            body = content.split("正文：", 1)[1].strip()
        return {"title": title, "body": body}

    def generate_titles(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        title: str,
        body: str,
        count: int,
    ) -> list[str]:
        content = self._complete(
            model_config=model_config,
            api_key=api_key,
            system_prompt="你是小红书标题优化专家。",
            user_prompt=f"请给出 {count} 个小红书标题，每行一个。\n原标题：{title}\n正文：{body}",
        )
        return [line.strip(" -0123456789.、") for line in content.splitlines() if line.strip()][:count]

    def generate_tags(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        title: str,
        body: str,
        count: int,
    ) -> list[str]:
        content = self._complete(
            model_config=model_config,
            api_key=api_key,
            system_prompt="你是小红书 SEO 和话题标签专家。",
            user_prompt=f"请给出 {count} 个小红书话题标签，只输出标签，用逗号或换行分隔。\n标题：{title}\n正文：{body}",
        )
        separators = content.replace("，", ",").replace("\n", ",").split(",")
        return [item.strip().lstrip("#") for item in separators if item.strip()][:count]

    def polish_text(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        text: str,
        instruction: str,
    ) -> str:
        return self._complete(
            model_config=model_config,
            api_key=api_key,
            system_prompt="你是小红书正文润色编辑。",
            user_prompt=f"润色要求：{instruction or '更自然、清晰、有种草感'}\n\n原文：\n{text}",
        )

    _AGENT_DRAFT_SCHEMA = {
        "type": "object",
        "properties": {
            "drafts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "image_prompt": {
                            "type": "object",
                            "properties": {
                                "positive_prompt": {"type": "string"},
                                "negative_prompt": {"type": "string"},
                                "reference_strategy": {"type": "string"},
                            },
                            "required": ["positive_prompt", "negative_prompt", "reference_strategy"],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["title", "body", "tags", "image_prompt"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["drafts"],
        "additionalProperties": False,
    }

    @staticmethod
    def _strip_fences(text: str) -> str:
        return re.sub(r"^```(?:json)?\s*\n?", "", re.sub(r"\n?```\s*$", "", text.strip()))

    @staticmethod
    def _validate_agent_draft_schema(data: dict) -> None:
        if "drafts" not in data or not isinstance(data["drafts"], list):
            raise ValueError("structured output missing 'drafts' array")
        for item in data["drafts"]:
            for key in ("title", "body", "tags", "image_prompt"):
                if key not in item:
                    raise ValueError(f"structured output item missing '{key}'")

    def _call_chat(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        messages: list[dict],
        temperature: float,
        top_p: float,
        extra_body: dict | None = None,
    ) -> str:
        if not model_config.base_url:
            raise ValueError("Text model base_url is required")
        if not model_config.model_name:
            raise ValueError("Text model_name is required")
        if not api_key:
            raise ValueError("Text model api_key is required")

        body: dict = {
            "model": model_config.model_name,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
        }
        if extra_body:
            body.update(extra_body)

        endpoint = f"{model_config.base_url.rstrip('/')}/chat/completions"
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("AI response missing choices[0].message.content") from exc

    def generate_agent_drafts(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        messages: list[dict],
        n: int,
        temperature: float,
        top_p: float,
        output_requirements: str | None,
        reference_image_urls: list[str],
    ) -> dict:
        prepared = list(messages)
        if output_requirements:
            for i, msg in enumerate(prepared):
                if msg.get("role") == "system":
                    updated = dict(msg)
                    updated["content"] = f"{msg['content']}\n\nOutput requirements: {output_requirements}"
                    prepared[i] = updated
                    break
            else:
                prepared.insert(0, {"role": "system", "content": f"Output requirements: {output_requirements}"})

        schema_body = {
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "xhs_agent_draft_batch",
                    "strict": True,
                    "schema": self._AGENT_DRAFT_SCHEMA,
                },
            }
        }

        # Pass 1: native structured output
        try:
            content = self._call_chat(
                model_config=model_config,
                api_key=api_key,
                messages=prepared,
                temperature=temperature,
                top_p=top_p,
                extra_body=schema_body,
            )
            data = json.loads(content)
            self._validate_agent_draft_schema(data)
            return data
        except (json.JSONDecodeError, ValueError):
            pass

        # Pass 2: prompt injection fallback
        schema_str = json.dumps(self._AGENT_DRAFT_SCHEMA, ensure_ascii=False)
        injection = (
            "\n\nYou must respond with a single valid JSON object and nothing else.\n"
            "Do not wrap the JSON in markdown code fences.\n"
            f"The JSON must conform to this schema:\n<schema>\n{schema_str}\n</schema>"
        )
        fallback_messages = list(prepared)
        injected = False
        for i, msg in enumerate(fallback_messages):
            if msg.get("role") == "system":
                fallback_messages[i] = dict(msg)
                fallback_messages[i]["content"] = str(msg["content"]) + injection
                injected = True
                break
        if not injected:
            fallback_messages.insert(0, {"role": "system", "content": injection.strip()})

        try:
            content = self._call_chat(
                model_config=model_config,
                api_key=api_key,
                messages=fallback_messages,
                temperature=temperature,
                top_p=top_p,
            )
            stripped = self._strip_fences(content)
            data = json.loads(stripped)
            self._validate_agent_draft_schema(data)
            return data
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"structured output failed after both passes: {exc}") from exc


class OpenAICompatibleImageClient:
    def _validate(self, *, model_config: ModelConfig, api_key: str) -> None:
        if not model_config.base_url:
            raise ValueError("Image model base_url is required")
        if not model_config.model_name:
            raise ValueError("Image model_name is required")
        if not api_key:
            raise ValueError("Image model api_key is required")

    def generate_cover(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        prompt: str,
        size: str,
        style: str,
    ) -> dict[str, Any]:
        return self.generate_image(
            model_config=model_config, api_key=api_key, prompt=f"{prompt}\nStyle: {style or 'clean XHS cover'}",
        )

    def generate_image(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        prompt: str,
        reference_images: list[str] | None = None,
    ) -> dict[str, Any]:
        self._validate(model_config=model_config, api_key=api_key)
        endpoint = f"{model_config.base_url.rstrip('/')}/images/generations"
        body: dict[str, Any] = {
            "model": model_config.model_name,
            "prompt": prompt,
            "response_format": "url",
        }
        if reference_images:
            resolved = [self._resolve_image_ref(url) for url in reference_images]
            if len(resolved) == 1:
                body["image"] = resolved[0]
            else:
                body["image"] = resolved
                body["sequential_image_generation"] = "disabled"
            body["watermark"] = False
        try:
            response = requests.post(
                endpoint,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
                timeout=180,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = ""
            try:
                detail = exc.response.json().get("error", {}).get("message", "") if exc.response else ""
            except Exception:
                pass
            raise ValueError(f"图片生成失败: {detail or exc}") from exc
        payload = response.json()
        try:
            item = payload["data"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("Image response missing data[0]") from exc
        image_ref = item.get("url") or item.get("b64_json")
        if not isinstance(image_ref, str) or not image_ref:
            raise ValueError("Image response missing url or b64_json")
        return {"url": image_ref, "raw": payload}

    @staticmethod
    def _resolve_image_ref(url: str) -> str:
        from pathlib import Path
        from backend.app.core.config import get_settings

        # Full HTTP(S) URLs - return as-is
        if url.startswith("http://") or url.startswith("https://"):
            return url

        # Data URLs - return as-is
        if url.startswith("data:"):
            return url

        # File protocol URLs - read local file
        if url.startswith("file://"):
            file_path = url[7:]  # Strip "file://"
            # Handle Windows paths (C:\path or /path)
            if len(file_path) > 2 and file_path[1] == ":":
                local = Path(file_path)
            else:
                local = Path(file_path.lstrip("/"))
            if local.is_file():
                return OpenAICompatibleImageClient._to_base64_data_url(local)
            return url

        # Backend API media paths - /api/files/media/{filename}
        if url.startswith("/api/files/media/"):
            file_name = url.split("/")[-1]
            local = Path(get_settings().storage_dir) / "media" / file_name
            if local.is_file():
                return OpenAICompatibleImageClient._to_base64_data_url(local)
            return url

        # Frontend media paths - media/{filename} or /media/{filename}
        media_path = url.lstrip("/")
        if media_path.startswith("media/"):
            local = Path(get_settings().storage_dir) / media_path
            if local.is_file():
                return OpenAICompatibleImageClient._to_base64_data_url(local)
            # Try as relative to storage_dir root
            local = Path(get_settings().storage_dir) / "media" / media_path.split("/")[-1]
            if local.is_file():
                return OpenAICompatibleImageClient._to_base64_data_url(local)

        # Relative URLs with frontend_url prefix
        settings = get_settings()
        if settings.frontend_url:
            frontend_url = settings.frontend_url.rstrip("/")
            if url.startswith(frontend_url):
                url = url[len(frontend_url):]
                if url.startswith("/api/files/media/"):
                    file_name = url.split("/")[-1]
                    local = Path(get_settings().storage_dir) / "media" / file_name
                    if local.is_file():
                        return OpenAICompatibleImageClient._to_base64_data_url(local)

        # Try direct path relative to storage_dir/media
        local = Path(get_settings().storage_dir) / "media" / url.split("/")[-1]
        if local.is_file():
            return OpenAICompatibleImageClient._to_base64_data_url(local)

        return url

    @staticmethod
    def _to_base64_data_url(local: Path) -> str:
        import base64
        raw = local.read_bytes()
        ext = local.suffix.lower().lstrip(".")
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp", "svg": "image/svg+xml"}.get(ext, "image/png")
        return f"data:{mime};base64,{base64.b64encode(raw).decode()}"

    def describe_image(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        image_url: str,
        instruction: str,
    ) -> str:
        self._validate(model_config=model_config, api_key=api_key)
        endpoint = f"{model_config.base_url.rstrip('/')}/chat/completions"
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model_config.model_name,
                "messages": [
                    {"role": "system", "content": "你是小红书图片分析助手。"},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": instruction or "描述这张图片适合的小红书卖点。"},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    },
                ],
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("AI response missing choices[0].message.content") from exc
        if not isinstance(content, str) or not content.strip():
            raise ValueError("AI image description is empty")
        return content.strip()
