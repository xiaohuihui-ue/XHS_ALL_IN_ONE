import type { EditAiImagePayload, ImageGenerationArtifact } from "../../../types";

export type BuildHomeDecorImageEditPayloadOptions = {
  sourceImageUrls: string[];
  editIntent: string;
  preserveText?: string;
  changeText?: string;
  avoidText?: string;
  roomType?: string | null;
  decorStyle?: string | null;
  imageCount?: number;
  size?: string | null;
  quality?: string | null;
  style?: string | null;
  responseFormat?: string | null;
  saveToAssets?: boolean;
};

export type ImageEditArtifactSummary = {
  status: string;
  resultUrls: string[];
  reportUrl?: string;
  reportFileName?: string;
  positivePrompt?: string;
  negativePrompt?: string;
  passed?: boolean;
  failedOrWarningChecks: string[];
  knowledgeBase?: string | null;
};

export type ImageEditReportPreview = {
  downloadUrl: string;
  fileName: string;
  title: string;
};

export function splitDesignInstructions(value: string | undefined): string[] {
  const seen = new Set<string>();
  const items: string[] = [];
  for (const raw of (value || "").split(/[\n,，;；]+/)) {
    const item = raw.trim();
    if (!item || seen.has(item)) continue;
    seen.add(item);
    items.push(item);
  }
  return items;
}

export function buildHomeDecorImageEditPayload(
  options: BuildHomeDecorImageEditPayloadOptions,
): EditAiImagePayload {
  return {
    source_images: options.sourceImageUrls.map((url, index) => ({
      id: `source-${index + 1}`,
      role: index === 0 ? "source_room" : "reference_room",
      url,
    })),
    task_type: "room_makeover",
    domain: "home_decor",
    edit_intent: options.editIntent.trim(),
    preserve: splitDesignInstructions(options.preserveText),
    change: splitDesignInstructions(options.changeText),
    avoid: splitDesignInstructions(options.avoidText),
    output_goal: "xhs_cover",
    realism_level: "high",
    room_type: options.roomType?.trim() || undefined,
    decor_style: options.decorStyle?.trim() || undefined,
    n: options.imageCount ?? 1,
    size: options.size || undefined,
    quality: options.quality || undefined,
    style: options.style || undefined,
    response_format: options.responseFormat || undefined,
    save_to_assets: options.saveToAssets ?? true,
  };
}

export function imageEditArtifactToSummary(artifact: ImageGenerationArtifact): ImageEditArtifactSummary {
  return {
    status: artifact.status,
    resultUrls: artifact.result_assets.map((asset) => asset.url).filter(Boolean),
    reportUrl: artifact.report?.download_url,
    reportFileName: artifact.report?.file_name,
    positivePrompt: artifact.compiled_prompts?.positive_prompt,
    negativePrompt: artifact.compiled_prompts?.negative_prompt,
    passed: artifact.quality_report?.passed,
    failedOrWarningChecks: (artifact.quality_report?.checks ?? [])
      .filter((check) => check.status !== "pass")
      .map((check) => check.name),
    knowledgeBase: artifact.provenance.knowledge_base,
  };
}

export function imageEditReportToPreview(
  summary: Pick<ImageEditArtifactSummary, "reportUrl" | "reportFileName">,
): ImageEditReportPreview | null {
  if (!summary.reportUrl || !summary.reportFileName) return null;
  return {
    downloadUrl: summary.reportUrl,
    fileName: summary.reportFileName,
    title: summary.reportFileName,
  };
}
