import assert from "node:assert/strict";
import fs from "node:fs/promises";
import test from "node:test";

async function readFrontendFile(path) {
  return fs.readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

function extractMenuItems(source, name) {
  const match = source.match(new RegExp(`const ${name}: MenuProps\\["items"\\] = \\[([\\s\\S]*?)\\];`));
  assert.ok(match, `${name} should be declared as a MenuProps items array`);
  return match[1];
}

function extractMenuKeys(menuSource) {
  return [...menuSource.matchAll(/key: "([^"]+)"/g)].map((match) => match[1]);
}

test("sidebar uses AI assistant as the first XHS entry and hides retired pages", async () => {
  const source = await readFrontendFile("src/components/layout/app-shell.tsx");
  const mainMenu = extractMenuItems(source, "mainNavItems");
  const footerMenu = extractMenuItems(source, "footerNavItems");
  const mainKeys = extractMenuKeys(mainMenu);
  const footerKeys = extractMenuKeys(footerMenu);

  assert.deepEqual(mainKeys.slice(0, 3), [
    "/platforms/xhs/agent-drafts",
    "/platforms/xhs/accounts",
    "/platforms/xhs/discovery",
  ]);

  assert.match(mainMenu, /label: "AI助手"/);
  assert.match(mainMenu, /label: "我的收藏"/);
  assert.match(mainMenu, /label: "我的创作"/);

  for (const hiddenKey of [
    "/platforms/xhs/dashboard",
    "/platforms/xhs/crawler",
    "/platforms/xhs/keywords",
    "/platforms/xhs/benchmarks",
    "/platforms/xhs/image-studio",
  ]) {
    assert.equal(mainKeys.includes(hiddenKey), false, `${hiddenKey} should be hidden from the sidebar`);
  }

  assert.equal(footerKeys.includes("/tasks"), false, "task center should be hidden from the footer nav");
});

test("default XHS entry points open the AI assistant page", async () => {
  const routerSource = await readFrontendFile("src/app/router.tsx");
  const guardSource = await readFrontendFile("src/components/ui/protected-route.tsx");
  const loginSource = await readFrontendFile("src/pages/login/login-page.tsx");
  const platformSelectorSource = await readFrontendFile("src/components/layout/platform-selector.tsx");

  assert.match(routerSource, /<Route path="\/" element=\{<Navigate to="\/platforms\/xhs\/agent-drafts" replace \/>}/);
  assert.match(guardSource, /<Navigate to="\/platforms\/xhs\/agent-drafts" replace \/>/);
  assert.equal(
    [...loginSource.matchAll(/navigate\("\/platforms\/xhs\/agent-drafts", \{ replace: true \}\);/g)].length,
    2,
    "login and register should always open the AI assistant after authentication",
  );
  assert.doesNotMatch(loginSource, /navigate\(from \|\|/);
  assert.match(platformSelectorSource, /platform\.id === "xhs"\s*\?\s*"\/platforms\/xhs\/agent-drafts"/);
});

test("page headers use the requested Chinese labels", async () => {
  const agentSource = await readFrontendFile("src/pages/platforms/xhs/agent-drafts-page.tsx");
  const librarySource = await readFrontendFile("src/pages/platforms/xhs/library-page.tsx");
  const draftsSource = await readFrontendFile("src/pages/platforms/xhs/rewrite-page.tsx");

  assert.match(agentSource, /title="AI助手"/);
  assert.match(librarySource, />我的收藏<\/Title>/);
  assert.match(draftsSource, /title="我的创作"/);
});
