import assert from "node:assert/strict";
import fs from "node:fs/promises";
import test from "node:test";

import ts from "typescript";

async function loadWorkflowModule() {
  const sourceUrl = new URL("../src/pages/platforms/xhs/agent-run-workflow.ts", import.meta.url);
  const source = await fs.readFile(sourceUrl, "utf8");
  const transpiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2020,
      target: ts.ScriptTarget.ES2020,
      jsx: ts.JsxEmit.ReactJSX,
    },
  });
  const encoded = Buffer.from(transpiled.outputText, "utf8").toString("base64");
  return import(`data:text/javascript;base64,${encoded}`);
}

const {
  agentRunToWorkflowSteps,
  agentRunReportToDownload,
  buildConfirmAgentRunPayload,
  buildXhsAgentRunPayload,
  savedNotesToReferenceOptions,
} = await loadWorkflowModule();

test("builds an OpenAI-compatible XHS Agent Run payload with research search options", () => {
  const payload = buildXhsAgentRunPayload({
    request: "Create two warm cream living-room posts.",
    refUrls: ["https://cdn.example.com/room-a.jpg", "https://cdn.example.com/room-b.jpg"],
    draftCount: 2,
    imagesPerDraft: 3,
    researchKeywordsText: "cream living room，small apartment\nstorage",
    researchSearchAccountId: 7,
    researchSearchLimit: 2,
    autoSaveResearch: true,
  });

  assert.equal(payload.n, 2);
  assert.equal(payload.image_options.n, 3);
  assert.equal(payload.metadata.platform, "xhs");
  assert.deepEqual(payload.metadata.research, {
    keywords: ["cream living room", "small apartment", "storage"],
    reference_note_ids: [],
    search_account_id: 7,
    search_limit: 2,
    auto_save: true,
  });

  assert.equal(payload.messages[0].role, "system");
  assert.equal(payload.messages[1].role, "user");
  assert.ok(Array.isArray(payload.messages[1].content));
  assert.deepEqual(payload.messages[1].content[0], {
    type: "text",
    text: "Create two warm cream living-room posts.",
  });
  assert.deepEqual(payload.messages[1].content[1], {
    type: "image_url",
    image_url: { url: "https://cdn.example.com/room-a.jpg" },
  });
});

test("includes selected XHS account id in Agent Run metadata", () => {
  const payload = buildXhsAgentRunPayload({
    request: "Create one post.",
    refUrls: [],
    draftCount: 1,
    imagesPerDraft: 0,
    accountId: 9,
  });

  assert.equal(payload.metadata.account_id, 9);
});

test("omits research search fields when no research keyword is configured", () => {
  const payload = buildXhsAgentRunPayload({
    request: "Create one breakfast post.",
    refUrls: [],
    draftCount: 1,
    imagesPerDraft: 0,
    researchKeywordsText: "  ",
    researchSearchAccountId: 7,
    researchSearchLimit: 3,
    autoSaveResearch: true,
  });

  assert.equal(payload.n, 1);
  assert.equal(payload.image_options.n, 0);
  assert.equal(payload.messages[1].content, "Create one breakfast post.");
  assert.deepEqual(payload.metadata, { platform: "xhs" });
});

test("normalizes selected saved note references into Agent Run research metadata", () => {
  const payload = buildXhsAgentRunPayload({
    request: "Create one saved-note based post.",
    refUrls: [],
    draftCount: 1,
    imagesPerDraft: 0,
    referenceNoteIds: [12, 12, 0, -3, 15],
    outputRequirements: "  保留参考笔记中的空间痛点和解决方案  ",
  });

  assert.deepEqual(payload.metadata.research, {
    keywords: [],
    reference_note_ids: [12, 15],
    search_account_id: undefined,
    search_limit: 0,
    auto_save: false,
  });
  assert.equal(payload.metadata.output_requirements, "保留参考笔记中的空间痛点和解决方案");
});

test("maps saved notes into compact reference select options", () => {
  assert.deepEqual(
    savedNotesToReferenceOptions([
      {
        id: 12,
        platform: "xhs",
        platform_account_id: 3,
        note_id: "note-a",
        title: "奶油风小户型收纳",
        content: "用墙面柜和柔光提升小客厅质感。",
        author_name: "室内设计师 A",
        created_at: "2026-05-17T12:00:00+08:00",
      },
      {
        id: 15,
        platform: "xhs",
        platform_account_id: 3,
        note_id: "note-b",
        title: "",
        content: "低预算改造案例。",
        author_name: "",
        created_at: "2026-05-17T12:00:00+08:00",
      },
    ]),
    [
      { value: 12, label: "奶油风小户型收纳 / 室内设计师 A" },
      { value: 15, label: "note-b" },
    ],
  );
});

test("maps Agent Run results into visible workflow steps", () => {
  const steps = agentRunToWorkflowSteps({
    run_id: 99,
    status: "completed",
    result: {
      created_count: 1,
      failed_count: 0,
      items: [
        {
          draft: {
            id: 21,
            platform: "xhs",
            title: "Warm Cream Living Room",
            body: "Use layered materials and practical layout tips.",
            tags: [{ name: "interior" }],
            created_at: "2026-05-17T12:00:00+08:00",
          },
          assets: [
            {
              id: 31,
              draft_id: 21,
              asset_type: "image",
              url: "/api/files/media/room.png",
              local_path: "room.png",
              sort_order: 0,
            },
          ],
          status: "completed",
          errors: [],
          cover_strategy: {
            cover_goal: "xhs_cover",
            cover_type: "interior",
            visual_core: "cream sofa",
            title_space: "top",
            text_in_image: false,
          },
          image_prompt_spec: {
            L1_publish_goal: "xhs",
            L2_topic: "living room",
            L3_audience: "home owners",
            L4_main_subject: "cream sofa",
            L5_scene: "living room",
            L6_composition: "wide angle",
            L7_style: "modern cream",
            L8_color_lighting: "warm daylight",
            L9_emotion: "cozy",
            L10_details: "wood texture",
            L11_platform_adaptation: "xhs cover",
            L12_negative_constraints: "no text",
          },
          publish_tips: "Review image order before publishing.",
          final_image_prompt: "Warm modern cream living room, realistic daylight.",
          iteration_history: [],
          quality_check: {
            is_relevant_to_topic: true,
            has_text_or_garbled_text: false,
            has_logo_or_watermark: false,
            has_qrcode: false,
            has_sensitive_content: false,
            has_deformed_face_or_hands: false,
            is_xiaohongshu_cover_ready: true,
            has_title_space: true,
            need_retry: false,
            retry_reason: "",
            vision_check_status: "checked",
            vision_check_message: "视觉质检已完成",
          },
        },
      ],
    },
  });

  assert.equal(steps.length, 3);
  assert.deepEqual(steps[0], {
    type: "titles",
    status: "done",
    titles: ["Warm Cream Living Room"],
    recommended_title: "Warm Cream Living Room",
  });
  assert.equal(steps[1].type, "draft");
  assert.equal(steps[1].draft_id, 21);
  assert.equal(steps[1].publish_tips, "Review image order before publishing.");
  assert.equal(steps[2].type, "images");
  assert.equal(steps[2].final_image_prompt, "Warm modern cream living room, realistic daylight.");
  assert.equal(steps[2].assets.length, 1);
  assert.equal(steps[2].image_quality_check.vision_check_status, "checked");
});

test("maps failed Agent Run items without drafts into error workflow steps", () => {
  const steps = agentRunToWorkflowSteps({
    run_id: 99,
    status: "completed",
    result: {
      created_count: 1,
      failed_count: 1,
      items: [
        {
          draft: {
            id: 21,
            platform: "xhs",
            title: "Completed draft",
            body: "Draft body.",
            tags: [],
            created_at: "2026-05-17T12:00:00+08:00",
          },
          assets: [],
          status: "completed",
          errors: [],
        },
        {
          draft: null,
          assets: [],
          status: "failed",
          errors: ["Image prompt generation failed"],
        },
      ],
    },
  });

  assert.equal(steps.length, 4);
  assert.deepEqual(steps[0].titles, ["Completed draft"]);
  assert.equal(steps[3].type, "draft");
  assert.equal(steps[3].status, "error");
  assert.equal(steps[3].title, "草稿 2");
  assert.equal(steps[3].error, "Image prompt generation failed");
});

test("builds manual publish confirmation payload from all Agent Run drafts", () => {
  const payload = buildConfirmAgentRunPayload(
    {
      run_id: 99,
      status: "completed",
      result: {
        created_count: 2,
        failed_count: 0,
        items: [
          { draft: { id: 21 }, assets: [], status: "completed", errors: [] },
          { draft: { id: 22 }, assets: [], status: "completed", errors: [] },
        ],
      },
    },
    { platformAccountId: 5 },
  );

  assert.deepEqual(payload, {
    platform_account_id: 5,
    draft_ids: [21, 22],
    publish_mode: "immediate",
  });
});

test("builds manual publish confirmation payload from successful Agent Run drafts only", () => {
  const payload = buildConfirmAgentRunPayload(
    {
      run_id: 99,
      status: "completed",
      result: {
        created_count: 1,
        failed_count: 1,
        items: [
          { draft: { id: 21 }, assets: [], status: "completed", errors: [] },
          { draft: null, assets: [], status: "failed", errors: ["Draft failed"] },
        ],
      },
    },
    { platformAccountId: 5 },
  );

  assert.deepEqual(payload, {
    platform_account_id: 5,
    draft_ids: [21],
    publish_mode: "immediate",
  });
});

test("builds manual publish confirmation payload with publish options", () => {
  const payload = buildConfirmAgentRunPayload(
    {
      run_id: 99,
      status: "completed",
      result: {
        created_count: 1,
        failed_count: 0,
        items: [{ draft: { id: 21 }, assets: [], status: "completed", errors: [] }],
      },
    },
    {
      platformAccountId: 5,
      publishMode: "scheduled",
      scheduledAt: "2026-05-18T09:30:00+08:00",
      topicsText: "室内设计, 奶油风\n小户型, 室内设计",
      location: "  上海  ",
      isPrivate: true,
    },
  );

  assert.deepEqual(payload, {
    platform_account_id: 5,
    draft_ids: [21],
    publish_mode: "scheduled",
    scheduled_at: "2026-05-18T09:30:00+08:00",
    topics: ["室内设计", "奶油风", "小户型"],
    location: "上海",
    is_private: true,
    privacy_type: 1,
  });
});

test("extracts authenticated Agent Run report download metadata", () => {
  assert.deepEqual(
    agentRunReportToDownload({
      run_id: 99,
      status: "completed",
      report: {
        file_name: "xhs-report-u1-test.html",
        file_path: "storage/exports/xhs-report-u1-test.html",
        download_url: "/api/files/exports/xhs-report-u1-test.html",
      },
    }),
    {
      fileName: "xhs-report-u1-test.html",
      downloadUrl: "/api/files/exports/xhs-report-u1-test.html",
    },
  );
  assert.equal(agentRunReportToDownload({ run_id: 99, status: "completed" }), null);
});
