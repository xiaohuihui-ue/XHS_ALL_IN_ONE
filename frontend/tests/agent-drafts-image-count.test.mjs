import assert from "node:assert/strict";
import fs from "node:fs/promises";
import test from "node:test";

async function readFrontendFile(path) {
  return fs.readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

test("AI assistant image count defaults to the shared random 3 to 5 range", async () => {
  const pageSource = await readFrontendFile("src/pages/platforms/xhs/agent-drafts-page.tsx");
  const hookSource = await readFrontendFile("src/hooks/use-draft-generation.ts");
  const rewriteSource = await readFrontendFile("src/pages/platforms/xhs/rewrite-page.tsx");

  assert.match(pageSource, /useState\(\(\) => getRandomImagesPerDraft\(\)\)/);
  assert.match(pageSource, /min=\{MIN_IMAGES_PER_DRAFT\} max=\{MAX_IMAGES_PER_DRAFT\}/);
  assert.doesNotMatch(pageSource, /useState\(1\)/);

  assert.match(hookSource, /options\.imagesPerDraft \?\? getRandomImagesPerDraft\(\)/);
  assert.doesNotMatch(hookSource, /imagesPerDraft = 1/);

  assert.match(rewriteSource, /useState\(\(\) => getRandomImagesPerDraft\(\)\)/);
});

test("shared frontend image count constants define the 3 to 5 range", async () => {
  const source = await readFrontendFile("src/lib/image-count.ts");

  assert.match(source, /MIN_IMAGES_PER_DRAFT = 3/);
  assert.match(source, /MAX_IMAGES_PER_DRAFT = 5/);
  assert.match(source, /Math\.random\(\)/);
});
