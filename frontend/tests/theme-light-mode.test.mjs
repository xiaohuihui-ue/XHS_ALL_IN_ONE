import assert from "node:assert/strict";
import fs from "node:fs/promises";
import test from "node:test";

const sourceFiles = [
  "src/components/ai/draft-step-card.tsx",
  "src/components/layout/app-shell.tsx",
  "src/pages/login/login-page.tsx",
  "src/pages/models/model-config-page.tsx",
  "src/pages/platforms/xhs/accounts-page.tsx",
  "src/pages/platforms/xhs/agent-drafts-page.tsx",
  "src/pages/platforms/xhs/benchmarks-page.tsx",
  "src/pages/platforms/xhs/xhs-dashboard.tsx",
  "src/pages/platforms/xhs/keywords-page.tsx",
  "src/pages/platforms/xhs/publish-page.tsx",
  "src/pages/tasks/task-center-page.tsx",
  "src/global.css",
];

async function readFrontendFile(path) {
  return fs.readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

test("theme provider exposes CSS variables for custom light and dark surfaces", async () => {
  const providerSource = await readFrontendFile("src/app/providers.tsx");

  for (const token of [
    "--color-background-primary",
    "--color-background-secondary",
    "--color-background-elevated",
    "--color-border",
    "--color-border-secondary",
    "--color-text-primary",
    "--color-text-secondary",
    "--color-text-muted",
  ]) {
    assert.match(providerSource, new RegExp(token), `${token} should be written by the theme provider`);
  }
});

test("light-mode surfaces avoid dark-only hardcoded colors in affected UI files", async () => {
  for (const path of sourceFiles) {
    const source = await readFrontendFile(path);

    assert.doesNotMatch(source, /#(?:141414|1a1a1a|1f1f1f|262626|303030|303050|434343)/i, `${path} should use theme variables instead of dark panel colors`);
    assert.doesNotMatch(source, /rgba\(255,\s*255,\s*255/i, `${path} should use theme variables instead of white alpha text or borders`);
    assert.doesNotMatch(source, /theme="dark"/, `${path} should not force Ant Design components into dark theme`);
  }
});
