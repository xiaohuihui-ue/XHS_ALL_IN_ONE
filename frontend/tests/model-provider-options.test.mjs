import assert from "node:assert/strict";
import fs from "node:fs/promises";
import test from "node:test";

import ts from "typescript";

async function loadProviderOptionsModule() {
  const sourceUrl = new URL("../src/pages/models/model-provider-options.ts", import.meta.url);
  const source = await fs.readFile(sourceUrl, "utf8");
  const transpiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2020,
      target: ts.ScriptTarget.ES2020,
    },
  });
  const encoded = Buffer.from(transpiled.outputText, "utf8").toString("base64");
  return import(`data:text/javascript;base64,${encoded}`);
}

const {
  AOMENT_API_BASE_URL,
  AOMENT_IMAGE_MODEL_OPTIONS,
  defaultBaseUrlForProvider,
  defaultModelNameForProvider,
  isAomentProvider,
} = await loadProviderOptionsModule();

test("Aoment provider options expose fixed base URL and image model dropdown choices", () => {
  assert.equal(AOMENT_API_BASE_URL, "https://www.aoment.com/api/aoment/v1");
  assert.deepEqual(
    AOMENT_IMAGE_MODEL_OPTIONS.map((option) => option.value),
    ["image-n2-fast", "image-n2", "image-n1-fast", "image-n1", "image-o2", "image-o2-pro"],
  );
});

test("Aoment provider defaults image config to API-key-only setup", () => {
  assert.equal(isAomentProvider("aoment"), true);
  assert.equal(isAomentProvider("aoment-api"), true);
  assert.equal(isAomentProvider("openai-compatible"), false);
  assert.equal(defaultModelNameForProvider("image", "aoment"), "image-n2-fast");
  assert.equal(defaultBaseUrlForProvider("image", "aoment", ""), AOMENT_API_BASE_URL);
  assert.equal(defaultBaseUrlForProvider("image", "openai-compatible", "https://api.example.com/v1"), "https://api.example.com/v1");
});

test("model config page renders Aoment image models through a Select control", async () => {
  const pageUrl = new URL("../src/pages/models/model-config-page.tsx", import.meta.url);
  const source = await fs.readFile(pageUrl, "utf8");

  assert.match(source, /AOMENT_IMAGE_MODEL_OPTIONS/);
  assert.match(source, /<Select/);
  assert.match(source, /isAomentProvider\(form\.provider\)/);
});
