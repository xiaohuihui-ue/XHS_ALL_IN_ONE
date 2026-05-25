import assert from "node:assert/strict";
import fs from "node:fs/promises";
import test from "node:test";

const reportUrl = new URL(
  "../../docs/superpowers/reports/2026-05-16-xhs-agent-implementation-analysis.html",
  import.meta.url,
);

test("XHS Agent implementation analysis report marks current implementation and test status", async () => {
  const html = await fs.readFile(reportUrl, "utf8");

  assert.match(html, /<!doctype html>/i);
  assert.match(html, /<html lang="zh-CN">/);
  assert.match(html, /id="current-status"/);
  assert.match(html, /当前执行状态（2026-05-18 更新）/);
  assert.match(html, /当前没有记录到失败测试项/);

  assert.match(html, /<span class="priority p0">P0<\/span> 基线修正/);
  assert.match(html, /<span class="priority p0">P1<\/span> Agent 编排 MVP/);
  assert.match(html, /<span class="priority p1">P2<\/span> 搜索与保存接入/);
  assert.match(html, /<span class="priority p1">P3<\/span> 图片编辑正式化/);
  assert.match(html, /<span class="priority p1">P4<\/span> 发布准备与确认/);
  assert.match(html, /<span class="priority p2">P5<\/span> 自动运营增强/);

  assert.match(html, /<span class="tag done">已完成<\/span>/);
  assert.match(html, /<span class="tag partial">部分完成<\/span>/);
  assert.match(html, /<span class="tag todo">未完成<\/span>/);
  assert.match(html, /<span class="tag fail">未通过<\/span>/);

  assert.match(html, /python -m pytest tests\/backend -q/);
  assert.match(html, /204 passed/);
  assert.match(html, /22 warnings/);
  assert.match(html, /node --test frontend\\tests\\\*.test.mjs/);
  assert.match(html, /23 passed/);
  assert.match(html, /npm run build/);
  assert.match(html, /git diff --check/);

  assert.match(html, /model_configs\.capabilities/);
  assert.match(html, /image_generation_artifacts/);
  assert.match(html, /capabilities/);
  assert.match(html, /image_edit/);
  assert.match(html, /真实上游文生图 \/ 图生图成本调用/);
  assert.match(html, /真实小红书发布/);
  assert.match(html, /未执行，且默认不执行/);
});
