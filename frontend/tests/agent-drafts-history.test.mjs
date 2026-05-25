import assert from "node:assert/strict";
import fs from "node:fs/promises";
import test from "node:test";

async function readFrontendFile(path) {
  return fs.readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

test("AI assistant page stays on the assistant route after generation", async () => {
  const source = await readFrontendFile("src/pages/platforms/xhs/agent-drafts-page.tsx");

  assert.doesNotMatch(source, /useNavigate/);
  assert.doesNotMatch(source, /navigate\(\s*["']\/platforms\/xhs\/drafts/);
  assert.doesNotMatch(source, /window\.location/);
});

test("AI assistant page exposes a persistent right-side chat history rail", async () => {
  const source = await readFrontendFile("src/pages/platforms/xhs/agent-drafts-page.tsx");

  assert.match(source, /AGENT_ASSISTANT_HISTORY_KEY/);
  assert.match(source, /data-testid="agent-drafts-history"/);
  assert.match(source, /聊天记录/);
  assert.match(source, /所有AI助手/);
  assert.match(source, /localStorage\.getItem\(AGENT_ASSISTANT_HISTORY_KEY\)/);
  assert.match(source, /localStorage\.setItem\(AGENT_ASSISTANT_HISTORY_KEY/);
  assert.match(source, /setSelectedHistoryId/);
});
