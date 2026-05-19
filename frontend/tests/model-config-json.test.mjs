import assert from "node:assert/strict";
import test from "node:test";

import {
  createModelConfigBackupFileName,
  modelConfigBackupToJson,
  normalizeModelConfigBackup,
} from "../.tmp/model-config-json.mjs";

const textConfig = {
  name: "默认文本模型",
  model_type: "text",
  provider: "openai-compatible",
  model_name: "gpt-5.4",
  base_url: "https://api.example.com/v1",
  api_key: "sk-local-test",
  is_default: true,
  capabilities: ["text_generation"],
};

const imageConfig = {
  name: "默认图片模型",
  model_type: "image",
  provider: "openai-compatible",
  model_name: "gpt-image-1",
  base_url: "https://image.example.com/v1",
  api_key: "sk-image-test",
  is_default: true,
  capabilities: ["image_generation", "image_edit"],
};

test("exports all model configs as a versioned JSON backup", () => {
  const json = modelConfigBackupToJson([textConfig, imageConfig]);
  const exported = JSON.parse(json);

  assert.deepEqual(exported, {
    version: 1,
    configs: [textConfig, imageConfig],
  });
});

test("imports a versioned JSON backup into trimmed model config payloads", () => {
  const imported = normalizeModelConfigBackup({
    version: 1,
    configs: [
      {
        name: "  图片模型  ",
        model_type: "image",
        provider: " openai-compatible ",
        model_name: " gpt-image-1 ",
        base_url: " https://api.example.com/v1/ ",
        api_key: " sk-imported ",
        is_default: false,
      },
      textConfig,
    ],
  });

  assert.deepEqual(imported, [
    {
      name: "图片模型",
      model_type: "image",
      provider: "openai-compatible",
      model_name: "gpt-image-1",
      base_url: "https://api.example.com/v1/",
      api_key: "sk-imported",
      is_default: false,
      capabilities: ["image_generation", "image_edit"],
    },
    textConfig,
  ]);
});

test("accepts a direct array for hand-written JSON backup files", () => {
  assert.deepEqual(normalizeModelConfigBackup([textConfig, imageConfig]), [textConfig, imageConfig]);
});

test("adds default capabilities when a backup omits them", () => {
  const imported = normalizeModelConfigBackup([
    {
      ...textConfig,
      capabilities: undefined,
    },
    {
      ...imageConfig,
      capabilities: undefined,
    },
  ]);

  assert.deepEqual(imported[0].capabilities, ["text_generation"]);
  assert.deepEqual(imported[1].capabilities, ["image_generation", "image_edit"]);
});

test("rejects JSON without a supported model_type", () => {
  assert.throws(
    () =>
      normalizeModelConfigBackup([
        {
          ...textConfig,
          model_type: "video",
        },
      ]),
    /model_type/
  );
});

test("creates a stable JSON backup filename", () => {
  assert.match(createModelConfigBackupFileName(), /^model-configs-\d{8}-\d{6}\.json$/);
});
