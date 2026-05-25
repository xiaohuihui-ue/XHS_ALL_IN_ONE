export const MIN_IMAGES_PER_DRAFT = 3;
export const MAX_IMAGES_PER_DRAFT = 5;

export function getRandomImagesPerDraft() {
  return Math.floor(Math.random() * (MAX_IMAGES_PER_DRAFT - MIN_IMAGES_PER_DRAFT + 1)) + MIN_IMAGES_PER_DRAFT;
}

export function normalizeImagesPerDraft(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return getRandomImagesPerDraft();
  return Math.min(MAX_IMAGES_PER_DRAFT, Math.max(MIN_IMAGES_PER_DRAFT, Math.trunc(value)));
}
