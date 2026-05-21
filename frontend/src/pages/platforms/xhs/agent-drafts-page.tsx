import {
  CloseOutlined,
  LoadingOutlined,
  PaperClipOutlined,
  PictureOutlined,
  SendOutlined,
} from "@ant-design/icons";
import {
  Button,
  InputNumber,
  Space,
  Tooltip,
  Typography,
  Upload,
} from "antd";
import type { UploadFile } from "antd";
import TextArea from "antd/es/input/TextArea";
import { useState } from "react";

import { DraftStepCard } from "../../../components/ai/draft-step-card";
import { PageHeader } from "../../../components/layout/app-shell";
import { useDraftGeneration } from "../../../hooks/use-draft-generation";

const { Text } = Typography;

export function XhsAgentDraftsPage() {
  const [request, setRequest] = useState("");
  const [draftCount, setDraftCount] = useState(3);
  const [imagesPerDraft, setImagesPerDraft] = useState(1);
  const [refImages, setRefImages] = useState<UploadFile[]>([]);

  const { steps, running, run, stop } = useDraftGeneration();

  const handleGenerate = () => {
    if (!request.trim()) return;
    void run({ mode: "generate", request, refImages, draftCount, imagesPerDraft });
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
    <>
      <PageHeader
        eyebrow="XHS · AI"
        title="AI助手"
        description="描述内容需求，生成多篇小红书草稿及配套图片。"
      />

      {/* Workflow steps area */}
      <div style={{ minHeight: "calc(100vh - 420px)", marginBottom: 16 }}>
        {steps.length === 0 && !running && (
          <div style={{ textAlign: "center", padding: "64px 0", color: "var(--color-text-muted)" }}>
            <PictureOutlined style={{ fontSize: 40, display: "block", marginBottom: 10 }} />
            <Text type="secondary" style={{ fontSize: 13 }}>在下方输入需求，点击发送开始生成</Text>
          </div>
        )}
        {steps.map((step, i) => <DraftStepCard key={i} step={step} />)}
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
                  min={1} max={5} value={imagesPerDraft}
                  onChange={(v) => setImagesPerDraft(v ?? 1)}
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
    </>
  );
}
