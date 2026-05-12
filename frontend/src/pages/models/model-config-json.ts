import type { ModelConfigPayload, ModelType } from "../../types";

export type ModelConfigBackup = {
  version: 1;
  configs: ModelConfigPayload[];
};

const validModelTypes: ModelType[] = ["text", "image"];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readString(source: Record<string, unknown>, field: keyof ModelConfigPayload): string {
  const value = source[field];
  if (typeof value !== "string") {
    throw new Error(`${field} must be a string`);
  }
  return value.trim();
}

function readModelType(source: Record<string, unknown>): ModelType {
  const value = readString(source, "model_type");
  if (!validModelTypes.includes(value as ModelType)) {
    throw new Error('model_type must be "text" or "image"');
  }
  return value as ModelType;
}

function readBoolean(source: Record<string, unknown>, field: keyof ModelConfigPayload): boolean {
  const value = source[field];
  if (typeof value !== "boolean") {
    throw new Error(`${field} must be a boolean`);
  }
  return value;
}

function normalizeModelConfigPayload(raw: unknown): ModelConfigPayload {
  if (!isRecord(raw)) {
    throw new Error("config must be an object");
  }
  return {
    name: readString(raw, "name"),
    model_type: readModelType(raw),
    provider: readString(raw, "provider"),
    model_name: readString(raw, "model_name"),
    base_url: readString(raw, "base_url"),
    api_key: readString(raw, "api_key"),
    is_default: readBoolean(raw, "is_default"),
  };
}

function readBackupItems(raw: unknown): unknown[] {
  if (Array.isArray(raw)) {
    return raw;
  }
  if (!isRecord(raw)) {
    throw new Error("JSON root must be an object");
  }
  if (Array.isArray(raw.configs)) {
    return raw.configs;
  }
  if ("config" in raw) {
    return [raw.config];
  }
  throw new Error("configs must be an array");
}

export function normalizeModelConfigBackup(raw: unknown): ModelConfigPayload[] {
  const configs = readBackupItems(raw).map(normalizeModelConfigPayload);
  if (configs.length === 0) {
    throw new Error("configs must include at least one model config");
  }
  return configs;
}

export function createModelConfigBackup(configs: ModelConfigPayload[]): ModelConfigBackup {
  return {
    version: 1,
    configs: configs.map((config) => ({ ...config })),
  };
}

export function modelConfigBackupToJson(configs: ModelConfigPayload[]): string {
  return JSON.stringify(createModelConfigBackup(configs), null, 2);
}

export function createModelConfigBackupFileName(date = new Date()): string {
  const timestamp = date.toISOString().replace(/\D/g, "").slice(0, 14);
  return `model-configs-${timestamp.slice(0, 8)}-${timestamp.slice(8)}.json`;
}
