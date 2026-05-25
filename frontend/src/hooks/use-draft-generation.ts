import type { UploadFile } from "antd";
import { useCallback, useRef, useState } from "react";

import type {
  AgentDraftItem,
  CoverStrategy,
  ImagePromptSpec,
  IterationRound,
  ImageQualityCheck,
} from "../types";
import { getRandomImagesPerDraft } from "../lib/image-count";
import { generateAgentDrafts, uploadAssetFile } from "../lib/api";
import { withRetry } from "../lib/retry";

export type DraftGenerationMode = "generate" | "rewrite";

export interface DraftGenerationOptions {
  mode: DraftGenerationMode;
  request: string;
  refImages?: UploadFile[];
  draftCount?: number;
  imagesPerDraft?: number;
  existingTitle?: string;
  existingBody?: string;
  rewriteInstruction?: string;
}


export interface TitlesStep {
  type: "titles";
  status: "running" | "retrying" | "done" | "error";
  retryCount?: number;
  titles?: string[];
  recommended_title?: string;
  topics?: string[];
  recommended_topic?: string;
  error?: string;
}

export interface DraftStep {
  type: "draft";
  index: number;
  title: string;
  status: "running" | "retrying" | "done" | "error";
  retryCount?: number;
  draft_id?: number;
  body?: string;
  tags?: Array<{ name: string }>;
  cover_strategy?: CoverStrategy;
  image_prompt_spec?: ImagePromptSpec;
  publish_tips?: string;
  error?: string;
}

export interface ImagesStep {
  type: "images";
  index: number;
  title: string;
  status: "running" | "retrying" | "done" | "error";
  retryCount?: number;
  assets?: AgentDraftItem["assets"];
  final_image_prompt?: string;
  iteration_history?: IterationRound[];
  image_quality_check?: ImageQualityCheck;
  errors?: string[];
  error?: string;
}

export type WorkflowStep = TitlesStep | DraftStep | ImagesStep;

const SYSTEM_PROMPT = `你是一个小红书内容策划与社群运营 Agent，擅长根据用户输入的文字需求和图片素材，生成适合小红书发布的完整笔记方案。

你的目标：
1. 理解用户的发布目的、目标人群、产品/活动/社群卖点。
2. 将用户需求拆解为小红书主题、标题、正文、标签、图片提示词。
3. 如果用户提供图片，需要结合图片内容进行分析和再创作。
4. 生成的小红书内容必须真实自然，避免生硬广告腔。
5. 文案要有小红书平台感，包括开头钩子、分段、emoji、痛点、收益、行动引导。
6. 图片提示词必须使用 12 层分层架构（L1-L12）。
7. 默认图片不直接生成文字，除非用户明确要求。
8. 不得生成违规、侵权、低俗、虚假承诺内容。
9. 输出内容需要结构化，方便后端调用生图模型。

工作流程：
- 第一步：分析输入需求和图片内容。
- 第二步：判断信息是否完整，如不完整，最多追问 3 个关键问题。
- 第三步：生成 3-5 个主题方向。
- 第四步：选择最适合的主题，生成 3-5 个标题。
- 第五步：生成完整小红书正文。
- 第六步：生成 8-12 个标签。
- 第七步：生成封面策略。
- 第八步：使用 12 层架构生成适合 gpt-image-2 的图片提示词。
- 第九步：对图片提示词进行质量评分。
- 第十步：调用生图工具生成图片。
- 第十一步：检查图片是否符合发布要求。
- 第十二步：输出最终小红书发布包。`;

function buildMessages(mode: DraftGenerationMode, options: DraftGenerationOptions, refUrls: string[]) {
  type Part = { type: "text"; text: string } | { type: "image_url"; image_url: { url: string } };

  let userText: string;
  if (mode === "rewrite") {
    userText = `改写以下小红书草稿。\n\n原标题：${options.existingTitle || ""}\n原正文：${options.existingBody || ""}\n\n改写要求：${options.rewriteInstruction || "保留事实，图片写实,，需要考虑空间连续和一致性，增强小红书种草感，语气自然。"}`;
  } else {
    userText = options.request;
  }

  const userContent: Part[] = [
    { type: "text", text: userText },
    ...refUrls.map((url): Part => ({ type: "image_url", image_url: { url } })),
  ];

  return [
    { role: "system" as const, content: SYSTEM_PROMPT },
    { role: "user" as const, content: refUrls.length > 0 ? userContent : userText },
  ];
}

export function useDraftGeneration() {
  const [steps, setSteps] = useState<WorkflowStep[]>([]);
  const [running, setRunning] = useState(false);
  const abortRef = useRef(false);

  const run = useCallback(async (options: DraftGenerationOptions) => {
    const { mode, refImages, draftCount = 3 } = options;
    const imagesPerDraft = options.imagesPerDraft ?? getRandomImagesPerDraft();
    abortRef.current = false;
    setRunning(true);
    setSteps([]);

    let refUrls: string[] = [];
    if (refImages && refImages.length > 0) {
      try {
        const uploads = await Promise.all(
          refImages.map((f) => uploadAssetFile(f.originFileObj as File))
        );
        refUrls = uploads.map((u) => u.download_url);
      } catch {
        setRunning(false);
        return;
      }
    }

    const messages = buildMessages(mode, options, refUrls);

    // Step 1: titles
    setSteps([{ type: "titles", status: "running" }]);
    let titles: string[] = [];
    let recommended_title = "";
    let topics: string[] = [];
    let recommended_topic = "";
    try {
      const res = (await withRetry(
        () => generateAgentDrafts({
          messages,
          n: draftCount,
          step: "titles",
          metadata: { platform: "xhs" },
        }),
        {
          onRetry: (attempt) => {
            setSteps([{ type: "titles", status: "retrying", retryCount: attempt }]);
          },
        },
      )) as Record<string, unknown>;
      titles = (res.titles as string[]) ?? [];
      recommended_title = (res.recommended_title as string) ?? titles[0] ?? "";
      topics = (res.topics as string[]) ?? [];
      recommended_topic = (res.recommended_topic as string) ?? topics[0] ?? "";
      setSteps([{
        type: "titles",
        status: "done",
        titles,
        recommended_title,
        topics,
        recommended_topic,
      }]);
    } catch (e) {
      setSteps([{
        type: "titles",
        status: "error",
        error: String(e),
        titles: [],
      }]);
      setRunning(false);
      return;
    }

    if (abortRef.current) { setRunning(false); return; }

    // Steps 2+: draft + images per title
    for (let i = 0; i < titles.length; i++) {
      if (abortRef.current) break;
      const title = titles[i];
      const draftStepIdx = i * 2 + 1;
      const imgStepIdx = i * 2 + 2;

      setSteps((prev) => [
        ...prev,
        { type: "draft", index: i, title, status: "running" } as DraftStep,
      ]);

      let draft_id: number | undefined;
      let body: string | undefined;
      let tags: Array<{ name: string }> | undefined;
      let cover_strategy: CoverStrategy | undefined;
      let image_prompt_spec: ImagePromptSpec | undefined;
      let publish_tips: string | undefined;

      try {
        const res = (await withRetry(
          () => generateAgentDrafts({
            messages,
            step: "draft",
            selected_title: title,
            metadata: { platform: "xhs" },
          }),
          {
            onRetry: (attempt) => {
              setSteps((prev) =>
                prev.map((s, i2) =>
                  i2 === draftStepIdx
                    ? { type: "draft", index: i, title, status: "retrying", retryCount: attempt }
                    : s,
                ),
              );
            },
          },
        )) as Record<string, unknown>;

        const draft_result = res.draft as AgentDraftItem["draft"] | undefined;
        draft_id = draft_result?.id;
        body = draft_result?.body;
        tags = draft_result?.tags;
        cover_strategy = res.cover_strategy as CoverStrategy | undefined;
        image_prompt_spec = res.image_prompt_spec as ImagePromptSpec | undefined;
        publish_tips = (res.publish_tips as string) || undefined;

        const draftStep: DraftStep = {
          type: "draft",
          index: i,
          title,
          status: "done",
          draft_id,
          body,
          tags,
          cover_strategy,
          image_prompt_spec,
          publish_tips,
        };
        setSteps((prev) => prev.map((s, i2) => (i2 === draftStepIdx ? draftStep : s)));
      } catch (e) {
        const draftStep: DraftStep = {
          type: "draft",
          index: i,
          title,
          status: "error",
          error: String(e),
        };
        setSteps((prev) => prev.map((s, i2) => (i2 === draftStepIdx ? draftStep : s)));
        continue;
      }

      if (imagesPerDraft === 0) {
        setSteps((prev) => [
          ...prev,
          { type: "images", index: i, title, status: "done", errors: ["已跳过（每篇图片数量设为 0，未生成图片）"] } as ImagesStep,
        ]);
        continue;
      }

      if (!draft_id) continue;

      setSteps((prev) => [
        ...prev,
        { type: "images", index: i, title, status: "running" } as ImagesStep,
      ]);

      try {
        const res = (await withRetry(
          () => generateAgentDrafts({
            messages,
            step: "images",
            draft_id,
            cover_strategy: cover_strategy,
            image_prompt_spec: image_prompt_spec,
            draft_body: body ?? "",
            reference_image_urls: refUrls,
            image_options: { n: imagesPerDraft },
            metadata: { platform: "xhs" },
          }, 600000),
          {
            onRetry: (attempt) => {
              setSteps((prev) =>
                prev.map((s, i2) =>
                  i2 === imgStepIdx
                    ? { type: "images", index: i, title, status: "retrying", retryCount: attempt }
                    : s,
                ),
              );
            },
          },
        )) as Record<string, unknown>;

        const imgStep: ImagesStep = {
          type: "images",
          index: i,
          title,
          status: "done",
          assets: (res.assets as AgentDraftItem["assets"]) ?? [],
          iteration_history: (res.iteration_history as IterationRound[]) ?? [],
          image_quality_check: (res.quality_check as ImageQualityCheck) ?? undefined,
          errors: (res.errors as string[] | undefined) ?? [],
        };
        setSteps((prev) => prev.map((s, i2) => (i2 === imgStepIdx ? imgStep : s)));
      } catch (e) {
        const imgStep: ImagesStep = {
          type: "images",
          index: i,
          title,
          status: "error",
          error: String(e),
          assets: [],
        };
        setSteps((prev) => prev.map((s, i2) => (i2 === imgStepIdx ? imgStep : s)));
      }
    }

    setRunning(false);
  }, []);

  const stop = useCallback(() => { abortRef.current = true; }, []);

  return { steps, running, run, stop };
}
