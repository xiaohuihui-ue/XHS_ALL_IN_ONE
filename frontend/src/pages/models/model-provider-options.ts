import type { ModelType } from "../../types";

export const AOMENT_API_BASE_URL = "https://www.aoment.com/api/aoment/v1";

export const AOMENT_IMAGE_MODEL_OPTIONS = [
  { label: "image-n2-fast", value: "image-n2-fast" },
  { label: "image-n2", value: "image-n2" },
  { label: "image-n1-fast", value: "image-n1-fast" },
  { label: "image-n1", value: "image-n1" },
  { label: "image-o2", value: "image-o2" },
  { label: "image-o2-pro", value: "image-o2-pro" },
];

export const MODEL_PROVIDER_OPTIONS = [
  { label: "OpenAI Compatible", value: "openai-compatible" },
  { label: "Aoment API", value: "aoment" },
];

export function isAomentProvider(provider: string | undefined): boolean {
  return provider === "aoment" || provider === "aoment-api";
}

export function defaultModelNameForProvider(type: ModelType, provider: string): string {
  if (type === "image" && isAomentProvider(provider)) {
    return "image-n2-fast";
  }
  return type === "text" ? "gpt-5.4" : "";
}

export function defaultBaseUrlForProvider(type: ModelType, provider: string, currentBaseUrl: string): string {
  if (type === "image" && isAomentProvider(provider)) {
    return AOMENT_API_BASE_URL;
  }
  return currentBaseUrl;
}

export function providerOptionsForType(type: ModelType): typeof MODEL_PROVIDER_OPTIONS {
  if (type === "text") {
    return MODEL_PROVIDER_OPTIONS.filter((option) => option.value === "openai-compatible");
  }
  return MODEL_PROVIDER_OPTIONS;
}
