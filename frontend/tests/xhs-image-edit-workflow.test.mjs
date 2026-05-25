import assert from "node:assert/strict";
import fs from "node:fs/promises";
import test from "node:test";

import ts from "typescript";

async function loadWorkflowModule() {
  const sourceUrl = new URL("../src/pages/platforms/xhs/image-edit-workflow.ts", import.meta.url);
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
  buildHomeDecorImageEditPayload,
  imageEditReportToPreview,
  imageEditArtifactToSummary,
  splitDesignInstructions,
} = await loadWorkflowModule();

test("splits design instruction text into trimmed unique items", () => {
  assert.deepEqual(
    splitDesignInstructions("window position，ceiling height\nwindow position; wall line"),
    ["window position", "ceiling height", "wall line"],
  );
});

test("builds structured home-decor image edit payload", () => {
  const payload = buildHomeDecorImageEditPayload({
    sourceImageUrls: ["https://cdn.example.com/room.jpg", "/api/files/media/ref.png"],
    editIntent: "Make a warm modern cream living room for a Xiaohongshu cover.",
    preserveText: "window position, ceiling height",
    changeText: "sofa，wall color",
    avoidText: "dark tones\ntext in image",
    roomType: "living_room",
    decorStyle: "modern_cream",
    imageCount: 2,
    size: "1792x1024",
    quality: "hd",
    style: "natural",
    responseFormat: "url",
    saveToAssets: false,
  });

  assert.deepEqual(payload, {
    source_images: [
      { id: "source-1", role: "source_room", url: "https://cdn.example.com/room.jpg" },
      { id: "source-2", role: "reference_room", url: "/api/files/media/ref.png" },
    ],
    task_type: "room_makeover",
    domain: "home_decor",
    edit_intent: "Make a warm modern cream living room for a Xiaohongshu cover.",
    preserve: ["window position", "ceiling height"],
    change: ["sofa", "wall color"],
    avoid: ["dark tones", "text in image"],
    output_goal: "xhs_cover",
    realism_level: "high",
    room_type: "living_room",
    decor_style: "modern_cream",
    n: 2,
    size: "1792x1024",
    quality: "hd",
    style: "natural",
    response_format: "url",
    save_to_assets: false,
  });
});

test("summarizes image edit artifact for UI rendering", () => {
  const summary = imageEditArtifactToSummary({
    request_id: "abc",
    status: "completed",
    source_images: [{ id: "source-1", role: "source_room", url: "https://cdn.example.com/room.jpg" }],
    normalized_spec: {
      source_images: [{ id: "source-1", role: "source_room", url: "https://cdn.example.com/room.jpg" }],
      task_type: "room_makeover",
      domain: "home_decor",
      edit_intent: "Make the room warmer.",
      preserve: ["window"],
      change: ["sofa"],
      avoid: ["text"],
      output_goal: "xhs_cover",
      realism_level: "high",
      room_type: "living_room",
      decor_style: "modern_cream",
    },
    edit_plan: {
      layout_policy: "Preserve: window",
      style_policy: "Apply style: modern_cream",
      material_policy: "Material changes: sofa",
      lighting_policy: "Keep lighting direction consistent",
      composition_policy: "Optimize composition for xhs_cover",
      steps: [],
    },
    compiled_prompts: {
      positive_prompt: "Interior design image edit. Intent: Make the room warmer.",
      negative_prompt: "text, watermark",
      compiler_version: "image_prompt_compiler_v1",
    },
    result_assets: [{ url: "data:image/png;base64,abc" }],
    quality_report: {
      passed: true,
      checks: [
        { name: "structure_preserved", status: "pass", message: "Checked." },
        { name: "material_realism", status: "warning", message: "Review." },
      ],
    },
    provenance: {
      model_name: "image-test",
      created_at: "2026-05-17T12:00:00+08:00",
      knowledge_base: "home_decor_v1",
      prompt_compiler: "image_prompt_compiler_v1",
    },
    report: {
      file_name: "xhs-image-report-u1-test.html",
      file_path: "storage/exports/xhs-image-report-u1-test.html",
      download_url: "/api/files/exports/xhs-image-report-u1-test.html",
    },
    errors: [],
  });

  assert.deepEqual(summary, {
    status: "completed",
    resultUrls: ["data:image/png;base64,abc"],
    reportUrl: "/api/files/exports/xhs-image-report-u1-test.html",
    reportFileName: "xhs-image-report-u1-test.html",
    positivePrompt: "Interior design image edit. Intent: Make the room warmer.",
    negativePrompt: "text, watermark",
    passed: true,
    failedOrWarningChecks: ["material_realism"],
    knowledgeBase: "home_decor_v1",
  });
});

test("extracts image edit report preview metadata", () => {
  assert.deepEqual(
    imageEditReportToPreview({
      reportUrl: "/api/files/exports/xhs-image-report-u1-test.html",
      reportFileName: "xhs-image-report-u1-test.html",
    }),
    {
      downloadUrl: "/api/files/exports/xhs-image-report-u1-test.html",
      fileName: "xhs-image-report-u1-test.html",
      title: "xhs-image-report-u1-test.html",
    },
  );
  assert.equal(imageEditReportToPreview({ status: "completed", resultUrls: [], failedOrWarningChecks: [] }), null);
});
