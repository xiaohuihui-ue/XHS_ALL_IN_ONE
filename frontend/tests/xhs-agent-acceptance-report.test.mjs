import assert from "node:assert/strict";
import fs from "node:fs/promises";
import test from "node:test";

const reportUrl = new URL("../../docs/superpowers/reports/2026-05-17-xhs-agent-acceptance-report.html", import.meta.url);

test("XHS Agent acceptance report documents implementation and verification scope", async () => {
  const html = await fs.readFile(reportUrl, "utf8");

  assert.match(html, /<!doctype html>/i);
  assert.match(html, /<html lang="zh-CN">/);
  assert.match(html, /小红书 Agent 功能验收报告/);
  assert.match(html, /--color-text-primary/);
  assert.match(html, /--color-background-primary/);
  assert.match(html, /POST \/api\/xhs\/agent\/runs/);
  assert.match(html, /POST \/api\/ai\/images\/edit/);
  assert.match(html, /capabilities/);
  assert.match(html, /vision/);
  assert.match(html, /image_edit/);
  assert.match(html, /GET \/api\/files\/exports\//);
  assert.match(html, /Agent 账号检查/);
  assert.match(html, /metadata\.account_id/);
  assert.match(html, /部分失败状态/);
  assert.match(html, /draft=null/);
  assert.match(html, /图片质检状态/);
  assert.match(html, /未执行\/未完成视觉质检/);
  assert.match(html, /参考笔记选择/);
  assert.match(html, /发布选项/);
  assert.match(html, /预览 HTML 方案报告/);
  assert.match(html, /node --test frontend\\tests\\\*.test.mjs/);
  assert.match(html, /python -m pytest tests\/backend -q/);
  assert.match(html, /npm run build/);
  assert.match(html, /发布需人工确认/);
});
