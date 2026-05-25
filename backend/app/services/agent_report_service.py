from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.core.config import get_settings
from backend.app.models import User


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return html.escape(value)
    return html.escape(json.dumps(value, ensure_ascii=False))


def write_xhs_agent_report(current_user: User, payload: dict[str, Any]) -> dict[str, str]:
    export_dir = Path(get_settings().storage_dir) / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"xhs-report-u{current_user.id}-{uuid4().hex}.html"
    file_path = export_dir / file_name

    result = payload.get("result") or {}
    research = payload.get("research") or {}
    keywords = research.get("keywords") or []
    reference_notes = research.get("reference_notes") or []
    search = research.get("search") or {}
    keyword_html = "".join(f"<span class=\"tag\">{_text(keyword)}</span>" for keyword in keywords)
    note_html = "".join(
        f"""
        <li>
          <strong>{_text(note.get("title"))}</strong>
          <span class="muted"> · Note ID: {_text(note.get("note_id"))}</span>
          <span class="muted"> by {_text(note.get("author_name"))}</span>
          <p>{_text(note.get("content"))}</p>
        </li>
        """
        for note in reference_notes
        if isinstance(note, dict)
    )
    candidate_html = "".join(
        f"""
        <li>
          <strong>{_text(item.get("title"))}</strong>
          <span class="muted"> · {_text(item.get("note_id"))} · likes {_text(item.get("likes"))}</span>
        </li>
        """
        for item in (search.get("candidates") or [])
        if isinstance(item, dict)
    )
    research_html = ""
    if keywords or reference_notes:
        research_html = f"""
        <section class="card">
          <h2>Research References</h2>
          <div>{keyword_html}</div>
          <p class="muted">Search saved: {_text(search.get("saved_count"))} / candidates: {_text(search.get("candidate_count"))}</p>
          <ul>{candidate_html}</ul>
          <ul>{note_html}</ul>
        </section>
        """
    items = result.get("items") or []
    item_sections = []
    for index, item in enumerate(items, start=1):
        draft = item.get("draft") or {}
        tags = draft.get("tags") or []
        tag_html = "".join(f"<span class=\"tag\">#{_text(tag.get('name') if isinstance(tag, dict) else tag)}</span>" for tag in tags)
        assets = item.get("assets") or []
        asset_html = "".join(
            f"<li>{_text(asset.get('url') if isinstance(asset, dict) else asset)}</li>"
            for asset in assets
        )
        quality = item.get("quality_check") or item.get("image_quality_check") or {}
        quality_status = quality.get("vision_check_status") or ("checked" if quality else "")
        quality_message = quality.get("vision_check_message") or quality.get("retry_reason") or ""
        quality_html = ""
        if quality:
            quality_html = f"""
              <h4>图片质检</h4>
              <p>
                <strong>状态：</strong>{_text(quality_status)}
                <br />
                <strong>结论：</strong>{_text(quality_message or quality)}
              </p>
            """
        item_sections.append(
            f"""
            <article class="card">
              <h3>{index}. {_text(draft.get("title"))}</h3>
              <p class="muted">状态：{_text(item.get("status"))} · Draft ID：{_text(draft.get("id"))}</p>
              <p>{_text(draft.get("body"))}</p>
              <div>{tag_html}</div>
              <h4>最终图片提示词</h4>
              <p>{_text(item.get("final_image_prompt"))}</p>
              <h4>生成图片</h4>
              <ul>{asset_html or "<li>未生成图片</li>"}</ul>
              {quality_html}
            </article>
            """
        )

    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>小红书 Agent 执行报告</title>
  <style>
    :root {{
      --color-text-primary: #172033;
      --color-text-secondary: #5f6b7a;
      --color-background-primary: #f7f8fb;
      --color-background-secondary: #ffffff;
      --color-border: #d9e1ec;
      --color-accent: #d73f74;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --color-text-primary: #f3f6fb;
        --color-text-secondary: #a8b3c4;
        --color-background-primary: #111827;
        --color-background-secondary: #172033;
        --color-border: #314158;
        --color-accent: #f472a0;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
      color: var(--color-text-primary);
      background: var(--color-background-primary);
      line-height: 1.65;
    }}
    .page {{ max-width: 1040px; margin: 0 auto; padding: 28px 20px 48px; }}
    .hero, .card {{
      background: var(--color-background-secondary);
      border: 1px solid var(--color-border);
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 14px;
    }}
    h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 24px 0 12px; font-size: 20px; letter-spacing: 0; }}
    h3 {{ margin: 0 0 8px; font-size: 17px; letter-spacing: 0; }}
    h4 {{ margin: 14px 0 6px; font-size: 14px; letter-spacing: 0; }}
    .muted {{ color: var(--color-text-secondary); }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }}
    .metric {{ border: 1px solid var(--color-border); border-radius: 8px; padding: 10px; }}
    .tag {{
      display: inline-flex;
      margin: 4px 6px 0 0;
      padding: 2px 8px;
      border: 1px solid var(--color-border);
      border-radius: 999px;
      color: var(--color-accent);
      font-size: 12px;
    }}
    ul {{ padding-left: 20px; }}
    @media (max-width: 720px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <p class="muted">XHS Agent Run #{_text(payload.get("run_id"))}</p>
      <h1>小红书 Agent 执行报告</h1>
      <p>本报告记录账号检查、模型检查、草稿生成、图片生成和发布准备状态。真实发布未自动执行，需要人工确认。</p>
      <div class="grid">
        <div class="metric"><strong>运行状态</strong><br />{_text(payload.get("status"))}</div>
        <div class="metric"><strong>生成草稿</strong><br />{_text(result.get("created_count"))}</div>
        <div class="metric"><strong>失败数量</strong><br />{_text(result.get("failed_count"))}</div>
      </div>
    </section>

    <section class="card">
      <h2>检查结果</h2>
      <p><strong>账号：</strong>{_text(payload.get("account_check"))}</p>
      <p><strong>模型：</strong>{_text(payload.get("model_check"))}</p>
      <p><strong>发布准备：</strong>{_text(payload.get("publish_preview"))}</p>
    </section>

    {research_html}

    <section>
      <h2>生成结果</h2>
      {''.join(item_sections) or '<article class="card"><p>没有生成结果。</p></article>'}
    </section>
  </main>
</body>
</html>
"""
    file_path.write_text(html_text, encoding="utf-8")
    return {
        "file_name": file_name,
        "file_path": str(file_path),
        "download_url": f"/api/files/exports/{file_name}",
    }


def write_image_edit_report(current_user: User, artifact: dict[str, Any]) -> dict[str, str]:
    export_dir = Path(get_settings().storage_dir) / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"xhs-image-report-u{current_user.id}-{uuid4().hex}.html"
    file_path = export_dir / file_name

    spec = artifact.get("normalized_spec") or {}
    plan = artifact.get("edit_plan") or {}
    prompts = artifact.get("compiled_prompts") or {}
    quality = artifact.get("quality_report") or {}
    provenance = artifact.get("provenance") or {}
    source_images = artifact.get("source_images") or []
    result_assets = artifact.get("result_assets") or []
    checks = quality.get("checks") or []

    source_html = "".join(
        f"""
        <figure>
          <img src="{_text(item.get("url"))}" alt="{_text(item.get("role"))}" />
          <figcaption>{_text(item.get("id"))} / {_text(item.get("role"))}</figcaption>
        </figure>
        """
        for item in source_images
        if isinstance(item, dict)
    )
    result_html = "".join(
        f"""
        <figure>
          <img src="{_text(item.get("url"))}" alt="Generated result" />
          <figcaption>{_text(item.get("url"))}</figcaption>
        </figure>
        """
        for item in result_assets
        if isinstance(item, dict)
    )
    step_html = "".join(
        f"""
        <li>
          <strong>{_text(step.get("step"))}. {_text(step.get("name"))}</strong>
          <p>{_text(step.get("instruction"))}</p>
        </li>
        """
        for step in (plan.get("steps") or [])
        if isinstance(step, dict)
    )
    check_html = "".join(
        f"""
        <tr>
          <td>{_text(check.get("name"))}</td>
          <td><span class="status">{_text(check.get("status"))}</span></td>
          <td>{_text(check.get("message"))}</td>
        </tr>
        """
        for check in checks
        if isinstance(check, dict)
    )
    preserve_html = "".join(f"<span class=\"tag\">{_text(item)}</span>" for item in (spec.get("preserve") or []))
    change_html = "".join(f"<span class=\"tag\">{_text(item)}</span>" for item in (spec.get("change") or []))
    avoid_html = "".join(f"<span class=\"tag muted-tag\">{_text(item)}</span>" for item in (spec.get("avoid") or []))

    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Interior Design Image Report</title>
  <style>
    :root {{
      --color-text-primary: #18202f;
      --color-text-secondary: #607080;
      --color-background-primary: #f6f7f9;
      --color-background-secondary: #ffffff;
      --color-border: #d9e2ec;
      --color-accent: #c2415d;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --color-text-primary: #f5f7fb;
        --color-text-secondary: #aab6c5;
        --color-background-primary: #10151f;
        --color-background-secondary: #171f2c;
        --color-border: #314154;
        --color-accent: #fb7185;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--color-text-primary);
      background: var(--color-background-primary);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
      line-height: 1.65;
    }}
    .page {{ max-width: 1120px; margin: 0 auto; padding: 28px 20px 48px; }}
    .hero, .section {{
      background: var(--color-background-secondary);
      border: 1px solid var(--color-border);
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 14px;
    }}
    h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 0 0 12px; font-size: 20px; letter-spacing: 0; }}
    h3 {{ margin: 14px 0 6px; font-size: 15px; letter-spacing: 0; }}
    p {{ margin: 0 0 10px; }}
    .muted {{ color: var(--color-text-secondary); }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
    .gallery {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
    figure {{ margin: 0; border: 1px solid var(--color-border); border-radius: 8px; overflow: hidden; }}
    img {{ display: block; width: 100%; max-height: 360px; object-fit: contain; background: var(--color-background-primary); }}
    figcaption {{ padding: 8px 10px; color: var(--color-text-secondary); font-size: 12px; overflow-wrap: anywhere; }}
    .tag {{
      display: inline-flex;
      margin: 4px 6px 0 0;
      padding: 2px 8px;
      border: 1px solid var(--color-border);
      border-radius: 999px;
      color: var(--color-accent);
      font-size: 12px;
    }}
    .muted-tag {{ color: var(--color-text-secondary); }}
    .prompt {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      padding: 12px;
      border: 1px solid var(--color-border);
      border-radius: 8px;
      background: var(--color-background-primary);
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid var(--color-border); padding: 8px; text-align: left; vertical-align: top; }}
    .status {{ color: var(--color-accent); font-weight: 600; }}
    @media (max-width: 720px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <p class="muted">Request {_text(artifact.get("request_id"))}</p>
      <h1>Interior Design Image Report</h1>
      <p>本报告记录室内设计图生图的输入规格、编辑计划、Prompt 编译、生成结果、质量检查和模型来源，便于复盘与再次生成。</p>
      <div class="grid">
        <p><strong>Status</strong><br />{_text(artifact.get("status"))}</p>
        <p><strong>Model</strong><br />{_text(provenance.get("model_name"))}</p>
        <p><strong>Knowledge Base</strong><br />{_text(provenance.get("knowledge_base"))}</p>
        <p><strong>Prompt Compiler</strong><br />{_text(provenance.get("prompt_compiler"))}</p>
      </div>
    </section>

    <section class="section">
      <h2>Normalized Spec</h2>
      <p><strong>Task</strong>: {_text(spec.get("task_type"))} / <strong>Domain</strong>: {_text(spec.get("domain"))}</p>
      <p><strong>Intent</strong>: {_text(spec.get("edit_intent"))}</p>
      <p><strong>Room</strong>: {_text(spec.get("room_type"))} / <strong>Style</strong>: {_text(spec.get("decor_style"))}</p>
      <h3>Preserve</h3><div>{preserve_html or '<span class="muted">None</span>'}</div>
      <h3>Change</h3><div>{change_html or '<span class="muted">None</span>'}</div>
      <h3>Avoid</h3><div>{avoid_html or '<span class="muted">None</span>'}</div>
    </section>

    <section class="section">
      <h2>Source Images</h2>
      <div class="gallery">{source_html or '<p class="muted">No source images.</p>'}</div>
    </section>

    <section class="section">
      <h2>Edit Plan</h2>
      <p><strong>Layout</strong>: {_text(plan.get("layout_policy"))}</p>
      <p><strong>Style</strong>: {_text(plan.get("style_policy"))}</p>
      <p><strong>Material</strong>: {_text(plan.get("material_policy"))}</p>
      <p><strong>Lighting</strong>: {_text(plan.get("lighting_policy"))}</p>
      <p><strong>Composition</strong>: {_text(plan.get("composition_policy"))}</p>
      <ol>{step_html}</ol>
    </section>

    <section class="section">
      <h2>Compiled Prompts</h2>
      <h3>Positive Prompt</h3>
      <div class="prompt">{_text(prompts.get("positive_prompt"))}</div>
      <h3>Negative Prompt</h3>
      <div class="prompt">{_text(prompts.get("negative_prompt"))}</div>
    </section>

    <section class="section">
      <h2>Result Images</h2>
      <div class="gallery">{result_html or '<p class="muted">No generated images.</p>'}</div>
    </section>

    <section class="section">
      <h2>Quality Report</h2>
      <p><strong>Passed</strong>: {_text(quality.get("passed"))}</p>
      <table>
        <thead><tr><th>Check</th><th>Status</th><th>Message</th></tr></thead>
        <tbody>{check_html}</tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""
    file_path.write_text(html_text, encoding="utf-8")
    return {
        "file_name": file_name,
        "file_path": str(file_path),
        "download_url": f"/api/files/exports/{file_name}",
    }
