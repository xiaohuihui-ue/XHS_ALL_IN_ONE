from __future__ import annotations

import json
import re
from typing import Any, Protocol

import requests
from pydantic import BaseModel, Field

from backend.app.models import ModelConfig


# ----------------------------------------------------------------------
# Image prompt iteration models
# ----------------------------------------------------------------------


class ImagePromptSpec(BaseModel):
    L1_publish_goal: str = ""
    L2_topic: str = ""
    L3_audience: str = ""
    L4_main_subject: str = ""
    L5_scene: str = ""
    L6_composition: str = ""
    L7_style: str = ""
    L8_color_lighting: str = ""
    L9_emotion: str = ""
    L10_details: str = ""
    L11_platform_adaptation: str = ""
    L12_negative_constraints: str = ""


class PromptQualityScore(BaseModel):
    theme_clarity: int = Field(ge=1, le=5, default=3)
    subject_clarity: int = Field(ge=1, le=5, default=3)
    composition_control: int = Field(ge=1, le=5, default=3)
    xiaohongshu_fit: int = Field(ge=1, le=5, default=3)
    style_consistency: int = Field(ge=1, le=5, default=3)
    negative_constraints: int = Field(ge=1, le=5, default=3)
    text_risk: int = Field(ge=1, le=5, default=3)
    overall_score: float = Field(ge=1.0, le=5.0, default=3.0)


class ImageQualityCheck(BaseModel):
    is_relevant_to_topic: bool = True
    has_text_or_garbled_text: bool = False
    has_logo_or_watermark: bool = False
    has_qrcode: bool = False
    has_sensitive_content: bool = False
    has_deformed_face_or_hands: bool = False
    is_xiaohongshu_cover_ready: bool = True
    has_title_space: bool = True
    need_retry: bool = False
    retry_reason: str = ""


class IterationRound(BaseModel):
    iteration_round: int
    draft_prompt: str
    prompt_quality_score: PromptQualityScore
    failed_items: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)
    whether_need_rewrite: bool = False
    final_image_prompt: str = ""


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

    def generate_draft_titles(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        messages: list[dict],
        n: int,
        temperature: float,
        top_p: float,
    ) -> dict:
        """Generate n title candidates for XHS drafts, plus topics and recommendations."""
        ...

    def generate_single_draft(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        messages: list[dict],
        title: str,
        temperature: float,
        top_p: float,
        output_requirements: str | None,
    ) -> dict:
        """Generate a single draft with body, tags, cover_strategy, image_prompt_spec, and publish_tips."""
        ...

    def iterate_image_prompt(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        image_prompt_spec: dict,
        cover_strategy: dict,
        draft_body: str,
        reference_image_urls: list[str],
        max_iterations: int = 3,
        target_score: float = 4.5,
    ) -> dict:
        """
        Self-iterate image prompts via Planner/Generator/Critic/Rewriter loop.
        Returns: {"final_image_prompt": str, "iteration_history": list[dict], "total_rounds": int}
        """
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

    def generate_image_with_retry(
        self,
        *,
        prompt: str,
        reference_images: list[str] | None,
        image_model_config: ModelConfig,
        image_api_key: str,
        text_model_config: ModelConfig,
        text_api_key: str,
        topic: str,
        max_retries: int = 2,
    ) -> dict:
        """
        Generate an image, check quality, and retry on failure.
        Returns: {"url": str, "iteration_history": list[dict], "quality_check": dict}
        """
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

    def generate_draft_titles(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        messages: list[dict],
        n: int,
        temperature: float,
        top_p: float,
    ) -> dict:
        """Generate n title candidates for XHS drafts, plus topics and recommendations."""
        prepared = list(messages)
        injection = (
            f"\n\n请生成 {n} 个小红书标题候选（每个少于20字）和3-5个主题方向。"
            "以JSON格式返回："
            '{"titles": ["标题1", "标题2", ...], "topics": ["主题1", "主题2", ...]}'
            "\n推荐标题填入 titles[0]，推荐主题填入 topics[0]。"
        )
        for i, msg in enumerate(prepared):
            if msg.get("role") == "system":
                prepared[i] = dict(msg)
                prepared[i]["content"] = str(msg["content"]) + injection
                break
        else:
            prepared.insert(0, {"role": "system", "content": injection})

        try:
            content = self._call_chat(
                model_config=model_config,
                api_key=api_key,
                messages=prepared,
                temperature=temperature,
                top_p=top_p,
            )
            stripped = self._strip_fences(content)
            data = json.loads(stripped)
            if "titles" not in data or not isinstance(data["titles"], list):
                raise ValueError("structured output missing 'titles' array")
            titles = data["titles"][:n]
            topics = data.get("topics") or []
            return {
                "titles": titles,
                "recommended_title": titles[0] if titles else "",
                "topics": topics[:5],
                "recommended_topic": topics[0] if topics else "",
            }
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"title generation failed: {exc}") from exc

    def generate_single_draft(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        messages: list[dict],
        title: str,
        temperature: float,
        top_p: float,
        output_requirements: str | None,
    ) -> dict:
        """Generate a single draft with body, tags, cover_strategy, image_prompt_spec, and publish_tips."""
        prepared = list(messages)
        instruction = (
            f"基于标题「{title}」生成小红书草稿。"
            + (f" 要求：{output_requirements}" if output_requirements else "")
            + (
                "\n\n返回JSON格式（image_prompt_spec 使用12层结构）："
                '{"body": "正文内容（少于1000字）", '
                '"tags": ["标签1", "标签2", ...], '
                '"cover_strategy": {"cover_goal": "封面目标", "cover_type": "封面类型", "visual_core": "视觉核心", "title_space": "标题留白位置", "text_in_image": false}, '
                '"image_prompt_spec": {"L1_publish_goal": "", "L2_topic": "", "L3_audience": "", "L4_main_subject": "", "L5_scene": "", "L6_composition": "", "L7_style": "", "L8_color_lighting": "", "L9_emotion": "", "L10_details": "", "L11_platform_adaptation": "", "L12_negative_constraints": ""}, '
                '"publish_tips": "发布建议"}'
            )
        )

        for i, msg in enumerate(prepared):
            if msg.get("role") == "system":
                prepared[i] = dict(msg)
                prepared[i]["content"] = str(msg["content"]) + "\n\n" + instruction
                break
        else:
            prepared.insert(0, {"role": "system", "content": instruction})

        try:
            content = self._call_chat(
                model_config=model_config,
                api_key=api_key,
                messages=prepared,
                temperature=temperature,
                top_p=top_p,
            )
            stripped = self._strip_fences(content)
            data = json.loads(stripped)
            for key in ("body", "tags"):
                if key not in data:
                    raise ValueError(f"structured output missing '{key}'")
            return {
                "title": title,
                "body": data.get("body") or "",
                "tags": data.get("tags") or [],
                "cover_strategy": data.get("cover_strategy") or {},
                "image_prompt_spec": data.get("image_prompt_spec") or {},
                "publish_tips": data.get("publish_tips") or "",
            }
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"draft generation failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Image prompt self-iteration (Planner/Generator/Critic/Rewriter loop)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_image_prompt_spec(spec: dict, cover: dict, draft_body: str, ref_urls: list[str]) -> str:
        """Planner: format ImagePromptSpec + cover_strategy into a structured design brief."""
        lines = [
            "【图片生成需求分析】",
            f"正文摘要：{draft_body[:200]}",
            "",
            "【封面策略】",
            f"  封面目标：{cover.get('cover_goal', '')}",
            f"  封面类型：{cover.get('cover_type', '')}",
            f"  视觉核心：{cover.get('visual_core', '')}",
            f"  标题留白：{cover.get('title_space', '')}",
            "",
            "【12层图片提示词规格】",
        ]
        for key in [
            "L1_publish_goal", "L2_topic", "L3_audience", "L4_main_subject",
            "L5_scene", "L6_composition", "L7_style", "L8_color_lighting",
            "L9_emotion", "L10_details", "L11_platform_adaptation", "L12_negative_constraints",
        ]:
            val = spec.get(key, "") or ""
            if val:
                lines.append(f"  {key}：{val}")
        if ref_urls:
            lines.append(f"\n参考图片数量：{len(ref_urls)}（请在 prompt 中体现如何使用这些参考图）")
        return "\n".join(lines)

    @staticmethod
    def _generate_draft_prompt(brief: str, model: str, api_key: str, base_url: str) -> str:
        """Generator: produce a draft image prompt from a structured brief."""
        system_prompt = (
            "你是一个小红书封面图生图提示词工程师。根据以下结构化设计需求，"
            "生成一版适合 gpt-image-2 的高质量中文生图提示词。\n"
            "要求：\n"
            "1. 语言具体、可执行，不要抽象。\n"
            "2. 覆盖空间类型、装修风格、硬装、软装、材质、色彩、灯光、镜头构图。\n"
            "3. 图片必须适合小红书封面（竖版3:4，上方或侧边保留25%-30%干净留白）。\n"
            "4. 不要生成文字、Logo、水印、二维码。\n"
            "5. 不要豪宅化、酒店化、别墅化，保持普通住宅尺度。\n"
            "6. 如果有参考图片，说明如何在构图或风格上借鉴。\n"
            "7. 输出仅包含提示词正文，不要 markdown 包装。"
        )
        user_prompt = f"{brief}\n\n请生成生图提示词（纯文本，不要代码块包裹）："
        endpoint = f"{base_url.rstrip('/')}/chat/completions"
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
            },
            timeout=60,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return re.sub(r"^```(?:json)?\s*\n?", "", re.sub(r"\n?```\s*$", "", content.strip()))

    @staticmethod
    def _score_draft_prompt(
        draft_prompt: str, model: str, api_key: str, base_url: str
    ) -> dict:
        """Critic: score a draft prompt across 8 dimensions, return JSON dict."""
        system_prompt = (
            "你是一个小红书图片提示词质检员。请对以下生图提示词按8个维度评分（1-5分）。\n"
            "评分维度：\n"
            "1. theme_clarity - 主题清晰度\n"
            "2. subject_clarity - 主体清晰度\n"
            "3. composition_control - 构图可控性\n"
            "4. xiaohongshu_fit - 小红书封面适配度\n"
            "5. style_consistency - 风格一致性\n"
            "6. negative_constraints - 禁止项完整性\n"
            "7. text_risk - 文字风险（分数越高风险越低）\n"
            "8. overall_score - 综合评分\n\n"
            "请返回严格 JSON（不要 markdown 包裹）：\n"
            '{"scores": {"theme_clarity": int, "subject_clarity": int, "composition_control": int, '
            '"xiaohongshu_fit": int, "style_consistency": int, '
            '"negative_constraints": int, "text_risk": int}, '
            '"overall_score": float, '
            '"failed_items": [], '
            '"improvement_suggestions": [], '
            '"whether_need_rewrite": bool}'
        )
        endpoint = f"{base_url.rstrip('/')}/chat/completions"
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"待质检提示词：\n{draft_prompt}"},
                ],
                "temperature": 0.3,
            },
            timeout=60,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        stripped = re.sub(r"^```(?:json)?\s*\n?", "", re.sub(r"\n?```\s*$", "", content.strip()))
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            # Fallback: assume pass
            data = {"scores": {}, "overall_score": 5.0, "failed_items": [], "improvement_suggestions": [], "whether_need_rewrite": False}
        return data

    @staticmethod
    def _rewrite_draft_prompt(
        draft_prompt: str, failed_items: list, suggestions: list,
        model: str, api_key: str, base_url: str,
    ) -> str:
        """Rewriter: rewrite draft prompt fixing failed items."""
        system_prompt = (
            "你是一个小红书生图提示词改写专家。根据质检意见重写提示词。\n"
            "改写要求：\n"
            "1. 保留原始主题和核心风格。\n"
            "2. 修复所有 failed_items。\n"
            "3. 应用 improvement_suggestions 中的建议。\n"
            "4. 输出仅包含重写后的提示词（纯文本，不要 markdown 包裹）。\n"
            "5. 不要添加解释或说明。"
        )
        user_prompt = (
            f"原始提示词：\n{draft_prompt}\n\n"
            f"失败项：{', '.join(failed_items) if failed_items else '无'}\n"
            f"改进建议：{', '.join(suggestions) if suggestions else '无'}\n\n"
            "请输出重写后的提示词（纯文本）："
        )
        endpoint = f"{base_url.rstrip('/')}/chat/completions"
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.6,
            },
            timeout=60,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return re.sub(r"^```(?:json)?\s*\n?", "", re.sub(r"\n?```\s*$", "", content.strip()))

    def iterate_image_prompt(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        image_prompt_spec: dict,
        cover_strategy: dict,
        draft_body: str,
        reference_image_urls: list[str],
        max_iterations: int = 3,
        target_score: float = 4.5,
    ) -> dict:
        """
        Self-iterate image prompts: Planner -> Generator -> Critic -> Rewriter.
        Returns: {"final_image_prompt": str, "iteration_history": list[dict], "total_rounds": int}
        """
        if not model_config.base_url or not model_config.model_name or not api_key:
            # Fallback: just assemble from spec layers
            parts = []
            for key in [
                "L1_publish_goal", "L2_topic", "L3_audience", "L4_main_subject",
                "L5_scene", "L6_composition", "L7_style", "L8_color_lighting",
                "L9_emotion", "L10_details", "L11_platform_adaptation",
            ]:
                val = (image_prompt_spec or {}).get(key, "") or ""
                if val:
                    parts.append(val)
            neg = (image_prompt_spec or {}).get("L12_negative_constraints", "") or ""
            prompt = "; ".join(parts) + ("." if parts else draft_body[:200])
            if neg:
                prompt += f"\n避免：{neg}"
            return {"final_image_prompt": prompt, "iteration_history": [], "total_rounds": 0}

        brief = self._format_image_prompt_spec(image_prompt_spec, cover_strategy, draft_body, reference_image_urls)
        base_url = model_config.base_url
        model = model_config.model_name

        iteration_history: list[dict] = []
        current_prompt = ""
        round_num = 0

        for round_num in range(1, max_iterations + 1):
            # Generator: produce draft prompt
            current_prompt = self._generate_draft_prompt(brief, model, api_key, base_url)

            # Critic: score it
            score_data = self._score_draft_prompt(current_prompt, model, api_key, base_url)
            overall = score_data.get("overall_score", 3.0)
            failed_items = score_data.get("failed_items") or []
            suggestions = score_data.get("improvement_suggestions") or []
            need_rewrite = score_data.get("whether_need_rewrite", False)

            iteration_history.append({
                "iteration_round": round_num,
                "draft_prompt": current_prompt,
                "prompt_quality_score": {
                    "theme_clarity": (score_data.get("scores") or {}).get("theme_clarity", 3),
                    "subject_clarity": (score_data.get("scores") or {}).get("subject_clarity", 3),
                    "composition_control": (score_data.get("scores") or {}).get("composition_control", 3),
                    "xiaohongshu_fit": (score_data.get("scores") or {}).get("xiaohongshu_fit", 3),
                    "style_consistency": (score_data.get("scores") or {}).get("style_consistency", 3),
                    "negative_constraints": (score_data.get("scores") or {}).get("negative_constraints", 3),
                    "text_risk": (score_data.get("scores") or {}).get("text_risk", 3),
                    "overall_score": overall,
                },
                "failed_items": failed_items,
                "improvement_suggestions": suggestions,
                "whether_need_rewrite": need_rewrite,
                "final_image_prompt": current_prompt,
            })

            if overall >= target_score and not need_rewrite:
                break

            if round_num < max_iterations:
                current_prompt = self._rewrite_draft_prompt(
                    current_prompt, failed_items, suggestions, model, api_key, base_url
                )
                # Update brief to include rewritten version for next round
                brief += f"\n\n【第{round_num}轮修正后提示词】：{current_prompt}"

        # Add final round entry with rewritten prompt if we broke after rewrite
        if (
            iteration_history
            and iteration_history[-1]["draft_prompt"] != current_prompt
            and round_num > 0
        ):
            iteration_history[-1]["final_image_prompt"] = current_prompt

        return {
            "final_image_prompt": current_prompt,
            "iteration_history": iteration_history,
            "total_rounds": len(iteration_history),
        }


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

    def _check_generated_image_quality(
        self,
        *,
        image_url: str,
        topic: str,
        text_model_config: ModelConfig,
        text_api_key: str,
    ) -> ImageQualityCheck:
        """
        Use a vision-capable text model to check generated image quality.
        Returns an ImageQualityCheck dict.
        """
        if not text_model_config.base_url or not text_model_config.model_name or not text_api_key:
            # Cannot check: return default pass
            return ImageQualityCheck(
                is_relevant_to_topic=True,
                has_text_or_garbled_text=False,
                has_logo_or_watermark=False,
                has_qrcode=False,
                has_sensitive_content=False,
                has_deformed_face_or_hands=False,
                is_xiaohongshu_cover_ready=True,
                has_title_space=True,
                need_retry=False,
                retry_reason="",
            ).model_dump()

        endpoint = f"{text_model_config.base_url.rstrip('/')}/chat/completions"
        quality_prompt = (
            "请检查以下小红书封面图片的质量，返回严格JSON（不要markdown包裹）：\n"
            "{\n"
            '  "is_relevant_to_topic": bool,  // 图片是否与主题相关\n'
            '  "has_text_or_garbled_text": bool,  // 是否有乱码文字\n'
            '  "has_logo_or_watermark": bool,  // 是否有Logo水印\n'
            '  "has_qrcode": bool,  // 是否有二维码\n'
            '  "has_sensitive_content": bool,  // 是否有敏感内容\n'
            '  "has_deformed_face_or_hands": bool,  // 是否有人脸或手部畸形\n'
            '  "is_xiaohongshu_cover_ready": bool,  // 是否适合小红书封面\n'
            '  "has_title_space": bool,  // 是否有标题留白\n'
            '  "need_retry": bool,  // 是否需要重试\n'
            '  "retry_reason": ""  // 重试原因\n'
            "}\n"
            "重点检查：乱码文字、Logo水印二维码、人物畸形、构图比例、标题留白。"
        )
        try:
            response = requests.post(
                endpoint,
                headers={"Authorization": f"Bearer {text_api_key}", "Content-Type": "application/json"},
                json={
                    "model": text_model_config.model_name,
                    "messages": [
                        {"role": "system", "content": "你是一个小红书图片质检专家。"},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": f"图片主题：{topic}\n{quality_prompt}"},
                                {"type": "image_url", "image_url": {"url": image_url}},
                            ],
                        },
                    ],
                    "temperature": 0.3,
                },
                timeout=120,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            stripped = re.sub(r"^```(?:json)?\s*\n?", "", re.sub(r"\n?```\s*$", "", content.strip()))
            data = json.loads(stripped)
            return ImageQualityCheck(**data).model_dump()
        except Exception:
            # Quality check failed: default to no retry
            return ImageQualityCheck(need_retry=False, retry_reason="质检接口异常，默认通过").model_dump()

    def generate_image_with_retry(
        self,
        *,
        prompt: str,
        reference_images: list[str] | None,
        image_model_config: ModelConfig,
        image_api_key: str,
        text_model_config: ModelConfig,
        text_api_key: str,
        topic: str,
        max_retries: int = 2,
    ) -> dict:
        """
        Generate image, check quality, retry on failure.
        Returns: {"url": str, "iteration_history": list[dict], "quality_check": dict}
        """
        correction_strategies: list[tuple[str, str]] = [
            ("has_text_or_garbled_text", "不要生成任何文字、字母、数字、标牌、海报文字。"),
            ("has_logo_or_watermark", "不要生成Logo、水印、二维码。"),
            ("has_deformed_face_or_hands", "人物脸部或手部不得变形，保持自然比例。"),
            ("has_title_space == false", "画面上方保留30%干净墙面留白，不要让主体占满画面。"),
        ]

        current_prompt = prompt
        iteration_history: list[dict] = []
        final_url = ""
        final_check: dict = {}

        for attempt in range(max_retries + 1):
            # Generate image
            img_result = self.generate_image(
                model_config=image_model_config,
                api_key=image_api_key,
                prompt=current_prompt,
                reference_images=reference_images,
            )
            image_url = img_result.get("url") or ""

            # Check quality
            quality_check = self._check_generated_image_quality(
                image_url=image_url,
                topic=topic,
                text_model_config=text_model_config,
                text_api_key=text_api_key,
            )

            iteration_history.append({
                "attempt": attempt + 1,
                "prompt": current_prompt,
                "image_url": image_url,
                "quality_check": quality_check,
            })

            if not quality_check.get("need_retry", False):
                final_url = image_url
                final_check = quality_check
                break

            # Apply correction strategies
            corrections: list[str] = []
            for key, correction in correction_strategies:
                if key == "has_title_space == false":
                    if not quality_check.get("has_title_space", True):
                        corrections.append(correction)
                elif quality_check.get(key, False):
                    corrections.append(correction)

            if corrections and attempt < max_retries:
                current_prompt = current_prompt.rstrip() + "\n" + " ".join(corrections)
            else:
                final_url = image_url
                final_check = quality_check
                break

        return {
            "url": final_url,
            "iteration_history": iteration_history,
            "quality_check": final_check,
        }
