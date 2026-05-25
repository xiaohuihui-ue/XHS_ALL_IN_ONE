import type { WorkflowStep } from "../../../components/ai/draft-step-card";
import type {
  AgentDraftRequestMessage,
  ConfirmXhsAgentRunPayload,
  SavedNote,
  XhsAgentRunPayload,
  XhsAgentRunResult,
} from "../../../types";

const SYSTEM_PROMPT = [
  "You are a Xiaohongshu content and interior-design Agent.",
  "Generate practical draft posts, cover image prompts, and publish-ready assets.",
  "Preserve user facts and reference images. Do not auto-publish.",
].join(" ");

export type BuildXhsAgentRunPayloadOptions = {
  request: string;
  refUrls: string[];
  draftCount: number;
  imagesPerDraft: number;
  accountId?: number | null;
  researchKeywordsText?: string;
  researchSearchAccountId?: number | null;
  researchSearchLimit?: number;
  autoSaveResearch?: boolean;
  referenceNoteIds?: number[];
  outputRequirements?: string;
};

export type BuildConfirmAgentRunPayloadOptions = {
  platformAccountId?: number | null;
  publishMode?: "immediate" | "scheduled";
  scheduledAt?: string | null;
  topicsText?: string;
  location?: string;
  isPrivate?: boolean | null;
};

export type ReportDownload = {
  fileName: string;
  downloadUrl: string;
};

export function splitResearchKeywords(value: string | undefined): string[] {
  const seen = new Set<string>();
  const keywords: string[] = [];
  for (const raw of (value || "").split(/[\n,，;；]+/)) {
    const keyword = raw.trim();
    if (!keyword || seen.has(keyword)) continue;
    seen.add(keyword);
    keywords.push(keyword);
  }
  return keywords;
}

function normalizePositiveIds(values: number[] | undefined): number[] {
  const seen = new Set<number>();
  const ids: number[] = [];
  for (const value of values ?? []) {
    if (!Number.isInteger(value) || value <= 0 || seen.has(value)) continue;
    seen.add(value);
    ids.push(value);
  }
  return ids;
}

export function splitPublishTopics(value: string | undefined): string[] {
  const seen = new Set<string>();
  const topics: string[] = [];
  for (const raw of (value || "").split(/[\n,，;；]+/)) {
    const topic = raw.trim();
    if (!topic || seen.has(topic)) continue;
    seen.add(topic);
    topics.push(topic);
  }
  return topics;
}

export function savedNotesToReferenceOptions(notes: SavedNote[]): Array<{ value: number; label: string }> {
  return notes.map((note) => {
    const title = note.title?.trim() || note.note_id || `Note ${note.id}`;
    const author = note.author_name?.trim();
    return {
      value: note.id,
      label: author ? `${title} / ${author}` : title,
    };
  });
}

function buildMessages(request: string, refUrls: string[]): AgentDraftRequestMessage[] {
  const text = request.trim();
  const userContent =
    refUrls.length > 0
      ? [
          { type: "text" as const, text },
          ...refUrls.map((url) => ({ type: "image_url" as const, image_url: { url } })),
        ]
      : text;

  return [
    { role: "system", content: SYSTEM_PROMPT },
    { role: "user", content: userContent },
  ];
}

export function buildXhsAgentRunPayload(options: BuildXhsAgentRunPayloadOptions): XhsAgentRunPayload {
  const keywords = splitResearchKeywords(options.researchKeywordsText);
  const referenceNoteIds = normalizePositiveIds(options.referenceNoteIds);
  const hasResearch = keywords.length > 0 || referenceNoteIds.length > 0;
  const accountId = options.accountId ?? 0;
  const searchAccountId = options.researchSearchAccountId ?? null;
  const searchLimit = searchAccountId ? Math.max(0, options.researchSearchLimit ?? 0) : 0;
  const autoSave = Boolean(searchAccountId && options.autoSaveResearch && keywords.length > 0);

  const metadata: XhsAgentRunPayload["metadata"] = {
    platform: "xhs",
  };
  if (Number.isInteger(accountId) && accountId > 0) {
    metadata.account_id = accountId;
  }
  if (options.outputRequirements?.trim()) {
    metadata.output_requirements = options.outputRequirements.trim();
  }
  if (hasResearch) {
    metadata.research = {
      keywords,
      reference_note_ids: referenceNoteIds,
      search_account_id: searchAccountId || undefined,
      search_limit: searchLimit,
      auto_save: autoSave,
    };
  }

  return {
    messages: buildMessages(options.request, options.refUrls),
    n: options.draftCount,
    metadata,
    image_options: {
      n: options.imagesPerDraft,
    },
  };
}

export function agentRunToWorkflowSteps(run: XhsAgentRunResult | null | undefined): WorkflowStep[] {
  const items = run?.result?.items ?? [];
  if (items.length === 0) return [];

  const titles = items
    .map((item) => item.draft?.title)
    .filter((title): title is string => Boolean(title));
  const steps: WorkflowStep[] = [
    {
      type: "titles",
      status: "done",
      titles,
      recommended_title: titles[0],
    },
  ];

  items.forEach((item, index) => {
    const draftTitle = item.draft?.title || `草稿 ${index + 1}`;
    if (!item.draft) {
      steps.push({
        type: "draft",
        index,
        title: draftTitle,
        status: "error",
        error: item.errors?.join("; ") || "Agent draft generation failed",
      });
      return;
    }
    const imageQualityCheck = item.image_quality_check ?? item.quality_check;

    steps.push({
      type: "draft",
      index,
      title: draftTitle,
      status: item.status === "failed" ? "error" : "done",
      draft_id: item.draft.id,
      body: item.draft.body,
      tags: item.draft.tags,
      cover_strategy: item.cover_strategy,
      image_prompt_spec: item.image_prompt_spec,
      publish_tips: item.publish_tips,
      error: item.errors?.join("; ") || undefined,
    });
    steps.push({
      type: "images",
      index,
      title: draftTitle,
      status: item.errors?.length && item.assets.length === 0 ? "error" : "done",
      assets: item.assets,
      final_image_prompt: item.final_image_prompt,
      iteration_history: item.iteration_history,
      image_quality_check: imageQualityCheck,
      errors: item.errors,
      error: item.errors?.join("; ") || undefined,
    });
  });

  return steps;
}

export function buildConfirmAgentRunPayload(
  run: XhsAgentRunResult,
  options: BuildConfirmAgentRunPayloadOptions = {},
): ConfirmXhsAgentRunPayload {
  const draftIds = (run.result?.items ?? [])
    .map((item) => item.draft?.id)
    .filter((id): id is number => typeof id === "number");
  const payload: ConfirmXhsAgentRunPayload = {
    draft_ids: draftIds,
    publish_mode: options.publishMode ?? "immediate",
  };
  if (options.platformAccountId) {
    payload.platform_account_id = options.platformAccountId;
  }
  if (options.publishMode === "scheduled" && options.scheduledAt?.trim()) {
    payload.scheduled_at = options.scheduledAt.trim();
  }
  const topics = splitPublishTopics(options.topicsText);
  if (topics.length > 0) {
    payload.topics = topics;
  }
  if (options.location?.trim()) {
    payload.location = options.location.trim();
  }
  if (typeof options.isPrivate === "boolean") {
    payload.is_private = options.isPrivate;
    payload.privacy_type = options.isPrivate ? 1 : 0;
  }
  return payload;
}

export function agentRunReportToDownload(run: XhsAgentRunResult | null | undefined): ReportDownload | null {
  if (!run?.report?.file_name || !run.report.download_url) return null;
  return {
    fileName: run.report.file_name,
    downloadUrl: run.report.download_url,
  };
}
