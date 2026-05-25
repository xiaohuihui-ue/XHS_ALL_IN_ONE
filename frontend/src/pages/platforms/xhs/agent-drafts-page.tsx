import {
  CloseOutlined,
  DeleteOutlined,
  HistoryOutlined,
  LoadingOutlined,
  MessageOutlined,
  PaperClipOutlined,
  PictureOutlined,
  PlusOutlined,
  SendOutlined,
} from "@ant-design/icons";
import {
  Badge,
  Button,
  Empty,
  InputNumber,
  Space,
  Tooltip,
  Typography,
  Upload,
} from "antd";
import type { UploadFile } from "antd";
import TextArea from "antd/es/input/TextArea";
import { useEffect, useMemo, useRef, useState } from "react";

import { DraftStepCard } from "../../../components/ai/draft-step-card";
import { PageHeader } from "../../../components/layout/app-shell";
import { useDraftGeneration } from "../../../hooks/use-draft-generation";
import {
  getRandomImagesPerDraft,
  MAX_IMAGES_PER_DRAFT,
  MIN_IMAGES_PER_DRAFT,
  normalizeImagesPerDraft,
} from "../../../lib/image-count";
import type { WorkflowStep } from "../../../hooks/use-draft-generation";

const { Text } = Typography;

const AGENT_ASSISTANT_HISTORY_KEY = "xhs-agent-assistant-history-v1";
const MAX_HISTORY_ITEMS = 80;

type AssistantHistoryStatus = "running" | "done" | "error";

type AssistantHistoryItem = {
  id: string;
  request: string;
  title: string;
  draftCount: number;
  imagesPerDraft: number;
  refImageCount: number;
  createdAt: string;
  updatedAt: string;
  status: AssistantHistoryStatus;
  steps: WorkflowStep[];
};

function createHistoryId() {
  return `agent-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function toHistoryTitle(request: string, steps: WorkflowStep[]) {
  const titlesStep = steps.find((step) => step.type === "titles");
  if (titlesStep?.type === "titles") {
    const title = titlesStep.recommended_title || titlesStep.titles?.[0];
    if (title) return title;
  }
  const draftStep = steps.find((step) => step.type === "draft");
  if (draftStep?.type === "draft" && draftStep.title) return draftStep.title;
  const firstLine = request.trim().split(/\r?\n/)[0] || "新会话";
  return firstLine.length > 24 ? `${firstLine.slice(0, 24)}...` : firstLine;
}

function getHistoryStatus(steps: WorkflowStep[], running: boolean): AssistantHistoryStatus {
  if (running) return "running";
  return steps.some((step) => step.status === "error") ? "error" : "done";
}

function parseAssistantHistory(value: string | null): AssistantHistoryItem[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value) as AssistantHistoryItem[];
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item) => item && typeof item.id === "string" && typeof item.request === "string")
      .map((item) => ({
        ...item,
        title: item.title || toHistoryTitle(item.request, item.steps ?? []),
        steps: Array.isArray(item.steps) ? item.steps : [],
        status: item.status === "running" ? "done" : item.status || "done",
      }))
      .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
      .slice(0, MAX_HISTORY_ITEMS);
  } catch {
    return [];
  }
}

function loadAssistantHistory() {
  if (typeof localStorage === "undefined") return [];
  return parseAssistantHistory(localStorage.getItem(AGENT_ASSISTANT_HISTORY_KEY));
}

function saveAssistantHistory(items: AssistantHistoryItem[]) {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(AGENT_ASSISTANT_HISTORY_KEY, JSON.stringify(items.slice(0, MAX_HISTORY_ITEMS)));
}

function formatRelativeTime(value: string) {
  const diff = Date.now() - new Date(value).getTime();
  if (!Number.isFinite(diff) || diff < 60_000) return "刚刚";
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 60) return `${minutes}分`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}时`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}天`;
  const weeks = Math.floor(days / 7);
  return `${weeks}周`;
}

export function XhsAgentDraftsPage() {
  const [request, setRequest] = useState("");
  const [draftCount, setDraftCount] = useState(3);
  const [imagesPerDraft, setImagesPerDraft] = useState(() => getRandomImagesPerDraft());
  const [refImages, setRefImages] = useState<UploadFile[]>([]);
  const [historyItems, setHistoryItems] = useState<AssistantHistoryItem[]>(() => loadAssistantHistory());
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(() => loadAssistantHistory()[0]?.id ?? null);
  const currentRunIdRef = useRef<string | null>(null);

  const { steps, running, run, stop } = useDraftGeneration();
  const selectedHistoryItem = useMemo(
    () => historyItems.find((item) => item.id === selectedHistoryId) ?? null,
    [historyItems, selectedHistoryId],
  );
  const visibleSteps = selectedHistoryItem?.steps ?? steps;
  const visibleHistoryIsRunning = running && (!selectedHistoryItem || selectedHistoryItem.id === currentRunIdRef.current);

  useEffect(() => {
    saveAssistantHistory(historyItems);
  }, [historyItems]);

  useEffect(() => {
    const currentRunId = currentRunIdRef.current;
    if (!currentRunId || (!running && steps.length === 0)) return;

    const updatedAt = new Date().toISOString();
    setHistoryItems((items) =>
      items.map((item) =>
        item.id === currentRunId
          ? {
              ...item,
              title: toHistoryTitle(item.request, steps),
              updatedAt,
              status: getHistoryStatus(steps, running),
              steps,
            }
          : item,
      ),
    );

    if (!running) {
      currentRunIdRef.current = null;
    }
  }, [running, steps]);

  const handleGenerate = () => {
    if (!request.trim()) return;
    const now = new Date().toISOString();
    const entry: AssistantHistoryItem = {
      id: createHistoryId(),
      request: request.trim(),
      title: toHistoryTitle(request, []),
      draftCount,
      imagesPerDraft,
      refImageCount: refImages.length,
      createdAt: now,
      updatedAt: now,
      status: "running",
      steps: [],
    };
    currentRunIdRef.current = entry.id;
    setSelectedHistoryId(entry.id);
    setHistoryItems((items) => [entry, ...items].slice(0, MAX_HISTORY_ITEMS));
    void run({ mode: "generate", request, refImages, draftCount, imagesPerDraft });
  };

  const handleSelectHistory = (item: AssistantHistoryItem) => {
    setSelectedHistoryId(item.id);
    setRequest(item.request);
    setDraftCount(item.draftCount);
    setImagesPerDraft(normalizeImagesPerDraft(item.imagesPerDraft));
  };

  const handleNewChat = () => {
    setSelectedHistoryId(null);
    setRequest("");
    setImagesPerDraft(getRandomImagesPerDraft());
    setRefImages([]);
  };

  const handleClearHistory = () => {
    setHistoryItems([]);
    setSelectedHistoryId(null);
    currentRunIdRef.current = null;
  };

  const addRefImage = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      setRefImages((prev) => [
        ...prev,
        { uid: `${Date.now()}-${file.name}`, name: file.name, originFileObj: file, thumbUrl: e.target?.result as string } as UploadFile,
      ]);
    };
    reader.readAsDataURL(file);
  };

  return (
    <div style={{ display: "flex", gap: 20, alignItems: "stretch", flexWrap: "wrap" }}>
      <div style={{ flex: "1 1 680px", minWidth: 420 }}>
        <PageHeader
          eyebrow="XHS · AI"
          title="AI助手"
          description="描述内容需求，生成多篇小红书草稿及配套图片。"
        />

        {/* Workflow steps area */}
        <div style={{ minHeight: "calc(100vh - 420px)", marginBottom: 16 }}>
          {visibleSteps.length === 0 && !visibleHistoryIsRunning && (
            <div style={{ textAlign: "center", padding: "64px 0", color: "var(--color-text-muted)" }}>
              <PictureOutlined style={{ fontSize: 40, display: "block", marginBottom: 10 }} />
              <Text type="secondary" style={{ fontSize: 13 }}>在下方输入需求，点击发送开始生成</Text>
            </div>
          )}
          {visibleSteps.map((step, i) => <DraftStepCard key={`${selectedHistoryId ?? "current"}-${i}`} step={step} />)}
        </div>

        {/* Input area */}
        <div style={{ position: "sticky", bottom: 0, background: "var(--color-background-primary)", paddingTop: 8, paddingBottom: 4 }}>
          {/* Reference images row */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
            <Upload
              accept="image/*"
              showUploadList={false}
              multiple
              beforeUpload={(file) => { addRefImage(file); return false; }}
            >
              <Tooltip title="附加参考图给 AI 生图使用">
                <Button
                  icon={<PaperClipOutlined />}
                  size="small"
                  type={refImages.length > 0 ? "primary" : "default"}
                  ghost={refImages.length > 0}
                >
                  参考图{refImages.length > 0 ? `（${refImages.length}）` : ""}
                </Button>
              </Tooltip>
            </Upload>
            {refImages.map((f) => (
              <div key={f.uid} style={{ position: "relative", display: "inline-flex" }}>
                <img
                  src={f.thumbUrl ?? ""}
                  alt={f.name}
                  width={40}
                  height={40}
                  style={{ objectFit: "cover", borderRadius: 6, border: "1px solid var(--color-border)" }}
                />
                <Button
                  size="small"
                  type="text"
                  icon={<CloseOutlined style={{ fontSize: 10 }} />}
                  onClick={() => setRefImages((p) => p.filter((x) => x.uid !== f.uid))}
                  style={{
                    position: "absolute", top: -5, right: -5,
                    width: 16, height: 16, minWidth: 0, padding: 0,
                    background: "var(--color-background-elevated)", borderRadius: "50%",
                    border: "1px solid var(--color-border)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}
                />
              </div>
            ))}
          </div>

          {/* Input box */}
          <div style={{
            border: "1px solid var(--color-border)",
            borderRadius: 12,
            padding: "10px 14px",
            background: "var(--color-background-secondary)",
          }}>
            <TextArea
              value={request}
              onChange={(e) => setRequest(e.target.value)}
              placeholder="描述内容需求，例如：生成3篇低卡早餐种草笔记，受众是减脂人群，语气自然亲切…"
              autoSize={{ minRows: 2, maxRows: 6 }}
              variant="borderless"
              style={{ padding: 0, fontSize: 14, resize: "none" }}
              onPressEnter={(e) => { if (!e.shiftKey) { e.preventDefault(); handleGenerate(); } }}
            />
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 8 }}>
              <Space size={8} wrap>
                <Space size={4}>
                  <Text type="secondary" style={{ fontSize: 12 }}>草稿数</Text>
                  <InputNumber
                    min={1} max={10} value={draftCount}
                    onChange={(v) => setDraftCount(v ?? 3)}
                    size="small" style={{ width: 56 }}
                  />
                </Space>
                <Space size={4}>
                  <Text type="secondary" style={{ fontSize: 12 }}>每篇图片</Text>
                  <InputNumber
                    min={MIN_IMAGES_PER_DRAFT} max={MAX_IMAGES_PER_DRAFT} value={imagesPerDraft}
                    onChange={(v) => setImagesPerDraft(normalizeImagesPerDraft(v))}
                    size="small" style={{ width: 56 }}
                  />
                </Space>
              </Space>
              <Space>
                {running && (
                  <Button size="small" danger onClick={stop}>停止</Button>
                )}
                <Button
                  type="primary"
                  icon={running ? <LoadingOutlined /> : <SendOutlined />}
                  disabled={running || !request.trim()}
                  onClick={handleGenerate}
                  shape="circle"
                />
              </Space>
            </div>
          </div>
        </div>
      </div>

      <aside
        data-testid="agent-drafts-history"
        aria-label="AI助手聊天记录"
        style={{
          flex: "0 0 300px",
          width: 300,
          minWidth: 280,
          minHeight: "calc(100vh - 96px)",
          borderLeft: "1px solid var(--color-border)",
          paddingLeft: 16,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <Space size={8}>
            <HistoryOutlined style={{ color: "var(--color-accent)" }} />
            <div>
              <Text strong style={{ display: "block", fontSize: 14 }}>聊天记录</Text>
              <Text type="secondary" style={{ fontSize: 12 }}>所有AI助手</Text>
            </div>
          </Space>
          <Space size={4}>
            <Tooltip title="新对话">
              <Button size="small" type="text" icon={<PlusOutlined />} onClick={handleNewChat} />
            </Tooltip>
            {historyItems.length > 0 && (
              <Tooltip title="清空记录">
                <Button size="small" type="text" icon={<DeleteOutlined />} onClick={handleClearHistory} />
              </Tooltip>
            )}
          </Space>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10, color: "var(--color-text-secondary)" }}>
          <MessageOutlined />
          <Text type="secondary" style={{ fontSize: 12 }}>AI助手</Text>
          <Badge count={historyItems.length} style={{ backgroundColor: "var(--color-accent)" }} />
        </div>

        <div style={{ flex: 1, overflowY: "auto", paddingRight: 4 }}>
          {historyItems.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={<Text type="secondary" style={{ fontSize: 12 }}>暂无聊天记录</Text>}
              style={{ marginTop: 64 }}
            />
          ) : (
            historyItems.map((item) => {
              const selected = item.id === selectedHistoryId;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => handleSelectHistory(item)}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    border: 0,
                    borderRadius: 6,
                    background: selected ? "var(--color-accent-subtle)" : "transparent",
                    color: "var(--color-text-primary)",
                    cursor: "pointer",
                    padding: "8px 10px",
                    marginBottom: 4,
                    display: "grid",
                    gridTemplateColumns: "1fr auto",
                    gap: 8,
                  }}
                >
                  <span style={{ minWidth: 0 }}>
                    <Text
                      ellipsis
                      style={{
                        display: "block",
                        fontSize: 13,
                        color: selected ? "var(--color-accent)" : "var(--color-text-primary)",
                        lineHeight: "20px",
                      }}
                    >
                      {item.title}
                    </Text>
                    <Text type="secondary" ellipsis style={{ display: "block", fontSize: 11, lineHeight: "18px" }}>
                      {item.draftCount}篇 · 每篇{item.imagesPerDraft}图{item.refImageCount > 0 ? ` · 参考图${item.refImageCount}` : ""}
                    </Text>
                  </span>
                  <Text type="secondary" style={{ fontSize: 12, whiteSpace: "nowrap", lineHeight: "20px" }}>
                    {item.status === "running" ? "生成中" : formatRelativeTime(item.updatedAt)}
                  </Text>
                </button>
              );
            })
          )}
        </div>
      </aside>
    </div>
  );
}
