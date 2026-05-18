import {
  CloseOutlined,
  FileTextOutlined,
  LoadingOutlined,
  PaperClipOutlined,
  PictureOutlined,
  SendOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Checkbox,
  Divider,
  Input,
  InputNumber,
  Select,
  Space,
  Tag,
  Tooltip,
  Typography,
  Upload,
  message,
} from "antd";
import type { UploadFile } from "antd";
import TextArea from "antd/es/input/TextArea";
import { useEffect, useMemo, useState } from "react";

import { DraftStepCard } from "../../../components/ai/draft-step-card";
import { PageHeader } from "../../../components/layout/app-shell";
import {
  confirmXhsAgentRun,
  createXhsAgentRun,
  downloadExportFile,
  fetchAccounts,
  fetchSavedNotes,
  uploadAssetFile,
} from "../../../lib/api";
import type { ConfirmXhsAgentRunResult, PlatformAccount, SavedNote, XhsAgentRunResult } from "../../../types";
import {
  agentRunToWorkflowSteps,
  agentRunReportToDownload,
  buildConfirmAgentRunPayload,
  buildXhsAgentRunPayload,
  savedNotesToReferenceOptions,
} from "./agent-run-workflow";
import type { WorkflowStep } from "../../../components/ai/draft-step-card";

const { Paragraph, Text } = Typography;

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error);
}

function accountLabel(account: PlatformAccount): string {
  const subtype = account.sub_type ? ` / ${account.sub_type}` : "";
  return `${account.nickname || `Account ${account.id}`}${subtype}`;
}

function researchEnabled(run: XhsAgentRunResult | null): boolean {
  const research = run?.research;
  if (!research) return false;
  return (
    research.keywords.length > 0 ||
    research.reference_notes.length > 0 ||
    Boolean(research.search?.enabled)
  );
}

export function XhsAgentDraftsPage() {
  const [request, setRequest] = useState("");
  const [draftCount, setDraftCount] = useState(3);
  const [imagesPerDraft, setImagesPerDraft] = useState(1);
  const [refImages, setRefImages] = useState<UploadFile[]>([]);
  const [researchKeywords, setResearchKeywords] = useState("");
  const [researchSearchAccountId, setResearchSearchAccountId] = useState<number | null>(null);
  const [researchSearchLimit, setResearchSearchLimit] = useState(3);
  const [autoSaveResearch, setAutoSaveResearch] = useState(true);
  const [savedNotes, setSavedNotes] = useState<SavedNote[]>([]);
  const [selectedReferenceNoteIds, setSelectedReferenceNoteIds] = useState<number[]>([]);
  const [outputRequirements, setOutputRequirements] = useState("");
  const [agentAccountId, setAgentAccountId] = useState<number | null>(null);
  const [publishAccountId, setPublishAccountId] = useState<number | null>(null);
  const [publishMode, setPublishMode] = useState<"immediate" | "scheduled">("immediate");
  const [scheduledAt, setScheduledAt] = useState("");
  const [publishTopics, setPublishTopics] = useState("");
  const [publishLocation, setPublishLocation] = useState("");
  const [publishPrivate, setPublishPrivate] = useState(false);
  const [accounts, setAccounts] = useState<PlatformAccount[]>([]);
  const [steps, setSteps] = useState<WorkflowStep[]>([]);
  const [running, setRunning] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [agentRun, setAgentRun] = useState<XhsAgentRunResult | null>(null);
  const [confirmResult, setConfirmResult] = useState<ConfirmXhsAgentRunResult | null>(null);

  useEffect(() => {
    let active = true;
    fetchAccounts("xhs")
      .then((items) => {
        if (!active) return;
        setAccounts(items);
        const pcAccount = items.find((item) => item.sub_type === "pc");
        const creatorAccount = items.find((item) => item.sub_type === "creator") ?? items[0];
        const defaultAgentAccount = creatorAccount ?? pcAccount ?? items[0];
        setAgentAccountId(defaultAgentAccount?.id ?? null);
        setResearchSearchAccountId(pcAccount?.id ?? null);
        setPublishAccountId(creatorAccount?.id ?? null);
      })
      .catch(() => {
        if (active) setAccounts([]);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    fetchSavedNotes({ platform: "xhs", page_size: 50 })
      .then((result) => {
        if (active) setSavedNotes(result.items);
      })
      .catch(() => {
        if (active) setSavedNotes([]);
      });
    return () => {
      active = false;
    };
  }, []);

  const pcAccounts = useMemo(
    () => accounts.filter((account) => account.sub_type === "pc"),
    [accounts],
  );
  const publishAccounts = useMemo(
    () => accounts.filter((account) => account.platform === "xhs"),
    [accounts],
  );
  const referenceNoteOptions = useMemo(
    () => savedNotesToReferenceOptions(savedNotes),
    [savedNotes],
  );
  const reportDownload = useMemo(() => agentRunReportToDownload(agentRun), [agentRun]);

  const handleGenerate = async () => {
    if (!request.trim() || running) return;
    if (autoSaveResearch && researchKeywords.trim() && !researchSearchAccountId) {
      message.warning("请选择用于搜索保存的 PC 账号");
      return;
    }

    setRunning(true);
    setAgentRun(null);
    setConfirmResult(null);
    setSteps([{ type: "titles", status: "running" }]);

    try {
      const uploads = await Promise.all(
        refImages
          .map((file) => file.originFileObj)
          .filter((file): file is NonNullable<UploadFile["originFileObj"]> => Boolean(file))
          .map((file) => uploadAssetFile(file)),
      );
      const payload = buildXhsAgentRunPayload({
        request,
        refUrls: uploads.map((item) => item.download_url),
        draftCount,
        imagesPerDraft,
        accountId: agentAccountId,
        researchKeywordsText: researchKeywords,
        researchSearchAccountId,
        researchSearchLimit,
        autoSaveResearch,
        referenceNoteIds: selectedReferenceNoteIds,
        outputRequirements,
      });
      const result = await createXhsAgentRun(payload);
      setAgentRun(result);
      setSteps(agentRunToWorkflowSteps(result));
    } catch (error) {
      setSteps([{ type: "titles", status: "error", error: getErrorMessage(error) }]);
    } finally {
      setRunning(false);
    }
  };

  const handleConfirmPublish = async () => {
    if (!agentRun || confirming) return;
    const payload = buildConfirmAgentRunPayload(agentRun, {
      platformAccountId: publishAccountId,
      publishMode,
      scheduledAt,
      topicsText: publishTopics,
      location: publishLocation,
      isPrivate: publishPrivate,
    });
    if (!payload.draft_ids || payload.draft_ids.length === 0) {
      message.warning("当前 Agent Run 没有可确认的草稿");
      return;
    }

    setConfirming(true);
    try {
      const result = await confirmXhsAgentRun(agentRun.run_id, payload);
      setConfirmResult(result);
      message.success(`已创建 ${result.created_count} 个待发布任务`);
    } catch (error) {
      message.error(getErrorMessage(error));
    } finally {
      setConfirming(false);
    }
  };

  const handleDownloadReport = async () => {
    if (!reportDownload) return;
    try {
      await downloadExportFile(reportDownload.downloadUrl, reportDownload.fileName);
    } catch (error) {
      message.error(getErrorMessage(error));
    }
  };

  const addRefImage = (file: File) => {
    const reader = new FileReader();
    reader.onload = (event) => {
      setRefImages((prev) => [
        ...prev,
        {
          uid: `${Date.now()}-${file.name}`,
          name: file.name,
          originFileObj: file,
          thumbUrl: event.target?.result as string,
        } as UploadFile,
      ]);
    };
    reader.readAsDataURL(file);
  };

  return (
    <>
      <PageHeader
        eyebrow="XHS Agent"
        title="小红书 Agent"
        description="账号检查、搜索参考、生成草稿与图片、输出 HTML 报告，并在确认后创建待发布任务。"
      />

      <div style={{ minHeight: "calc(100vh - 520px)", marginBottom: 16 }}>
        {steps.length === 0 && !running && (
          <div style={{ textAlign: "center", padding: "64px 0", color: "rgba(255,255,255,0.18)" }}>
            <PictureOutlined style={{ fontSize: 40, display: "block", marginBottom: 10 }} />
            <Text type="secondary" style={{ fontSize: 13 }}>
              输入需求后开始生成
            </Text>
          </div>
        )}

        {agentRun?.account_check?.warnings instanceof Array && agentRun.account_check.warnings.length > 0 && (
          <Alert
            type="warning"
            showIcon
            message={agentRun.account_check.warnings.join("；")}
            style={{ marginBottom: 12 }}
          />
        )}

        {researchEnabled(agentRun) && (
          <div style={{
            marginBottom: 12,
            padding: "12px 14px",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: 8,
            background: "rgba(255,255,255,0.035)",
          }}>
            <Space direction="vertical" size={6} style={{ width: "100%" }}>
              <Space wrap>
                <Text style={{ fontSize: 13, fontWeight: 500 }}>搜索参考</Text>
                {(agentRun?.research?.keywords ?? []).map((keyword) => (
                  <Tag key={keyword} color="blue">{keyword}</Tag>
                ))}
                {agentRun?.research?.search?.enabled && (
                  <Tag color="green">
                    保存 {agentRun.research.search.saved_count ?? 0} / 候选 {agentRun.research.search.candidate_count ?? 0}
                  </Tag>
                )}
              </Space>
              {(agentRun?.research?.reference_notes ?? []).slice(0, 3).map((note) => (
                <Paragraph key={note.id} ellipsis={{ rows: 2 }} style={{ marginBottom: 0, fontSize: 12 }}>
                  {note.title} · {note.author_name}：{note.content}
                </Paragraph>
              ))}
            </Space>
          </div>
        )}

        {steps.map((step, index) => <DraftStepCard key={index} step={step} />)}

        {reportDownload && (
          <Space wrap style={{ marginTop: 8 }}>
            <Button
              icon={<FileTextOutlined />}
              onClick={() => void handleDownloadReport()}
            >
              下载 HTML 报告
            </Button>
            <Select
              allowClear
              placeholder="发布账号"
              value={publishAccountId ?? undefined}
              onChange={(value) => setPublishAccountId(value ?? null)}
              style={{ minWidth: 220 }}
              options={publishAccounts.map((account) => ({
                value: account.id,
                label: accountLabel(account),
              }))}
            />
            <Select
              value={publishMode}
              onChange={(value) => setPublishMode(value)}
              style={{ width: 120 }}
              options={[
                { value: "immediate", label: "立即" },
                { value: "scheduled", label: "定时" },
              ]}
            />
            {publishMode === "scheduled" && (
              <Input
                type="datetime-local"
                value={scheduledAt}
                onChange={(event) => setScheduledAt(event.target.value)}
                style={{ width: 190 }}
              />
            )}
            <Input
              value={publishTopics}
              onChange={(event) => setPublishTopics(event.target.value)}
              placeholder="话题"
              style={{ width: 180 }}
            />
            <Input
              value={publishLocation}
              onChange={(event) => setPublishLocation(event.target.value)}
              placeholder="位置"
              style={{ width: 140 }}
            />
            <Checkbox
              checked={publishPrivate}
              onChange={(event) => setPublishPrivate(event.target.checked)}
            >
              私密
            </Checkbox>
            <Button loading={confirming} onClick={handleConfirmPublish}>
              手动确认发布任务
            </Button>
          </Space>
        )}

        {confirmResult && (
          <Alert
            type="success"
            showIcon
            message={confirmResult.message}
            description={`已创建发布任务：${confirmResult.items.map((item) => `#${item.id}`).join("、")}`}
            style={{ marginTop: 12 }}
          />
        )}
      </div>

      <div style={{
        position: "sticky",
        bottom: 0,
        background: "var(--color-background-primary, #141414)",
        paddingTop: 8,
        paddingBottom: 4,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
          <Upload
            accept="image/*"
            showUploadList={false}
            multiple
            beforeUpload={(file) => {
              addRefImage(file);
              return false;
            }}
          >
            <Tooltip title="参考图">
              <Button
                icon={<PaperClipOutlined />}
                size="small"
                type={refImages.length > 0 ? "primary" : "default"}
                ghost={refImages.length > 0}
              >
                参考图{refImages.length > 0 ? ` ${refImages.length}` : ""}
              </Button>
            </Tooltip>
          </Upload>
          {refImages.map((file) => (
            <div key={file.uid} style={{ position: "relative", display: "inline-flex" }}>
              <img
                src={file.thumbUrl ?? ""}
                alt={file.name}
                width={40}
                height={40}
                style={{ objectFit: "cover", borderRadius: 6, border: "1px solid rgba(255,255,255,0.15)" }}
              />
              <Button
                size="small"
                type="text"
                icon={<CloseOutlined style={{ fontSize: 10 }} />}
                onClick={() => setRefImages((prev) => prev.filter((item) => item.uid !== file.uid))}
                style={{
                  position: "absolute",
                  top: -5,
                  right: -5,
                  width: 16,
                  height: 16,
                  minWidth: 0,
                  padding: 0,
                  background: "rgba(0,0,0,0.7)",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              />
            </div>
          ))}
        </div>

        <div style={{
          border: "1px solid rgba(255,255,255,0.15)",
          borderRadius: 8,
          padding: "10px 14px",
          background: "rgba(255,255,255,0.04)",
        }}>
          <TextArea
            value={request}
            onChange={(event) => setRequest(event.target.value)}
            placeholder="例如：生成 2 篇现代奶油风客厅改造小红书笔记，图片要适合室内设计封面"
            autoSize={{ minRows: 2, maxRows: 6 }}
            variant="borderless"
            style={{ padding: 0, fontSize: 14, resize: "none" }}
            onPressEnter={(event) => {
              if (!event.shiftKey) {
                event.preventDefault();
                void handleGenerate();
              }
            }}
          />

          <Divider style={{ margin: "8px 0" }} />

          <Space size={8} wrap style={{ width: "100%", justifyContent: "space-between" }}>
            <Space size={8} wrap>
              <Space size={4}>
                <Text type="secondary" style={{ fontSize: 12 }}>草稿</Text>
                <InputNumber
                  min={1}
                  max={3}
                  value={draftCount}
                  onChange={(value) => setDraftCount(value ?? 3)}
                  size="small"
                  style={{ width: 56 }}
                />
              </Space>
              <Space size={4}>
                <Text type="secondary" style={{ fontSize: 12 }}>图片</Text>
                <InputNumber
                  min={0}
                  max={3}
                  value={imagesPerDraft}
                  onChange={(value) => setImagesPerDraft(value ?? 1)}
                  size="small"
                  style={{ width: 56 }}
                />
              </Space>
              <Select
                allowClear
                placeholder="Agent 账号检查"
                value={agentAccountId ?? undefined}
                onChange={(value) => setAgentAccountId(value ?? null)}
                size="small"
                style={{ minWidth: 180 }}
                options={publishAccounts.map((account) => ({
                  value: account.id,
                  label: accountLabel(account),
                }))}
              />
              <Input
                value={researchKeywords}
                onChange={(event) => setResearchKeywords(event.target.value)}
                placeholder="搜索关键词，用逗号分隔"
                size="small"
                style={{ width: 220 }}
              />
              <Select
                mode="multiple"
                allowClear
                maxTagCount="responsive"
                value={selectedReferenceNoteIds}
                onChange={(value) => setSelectedReferenceNoteIds(value)}
                placeholder="参考笔记"
                size="small"
                style={{ minWidth: 220 }}
                options={referenceNoteOptions}
              />
              <Input
                value={outputRequirements}
                onChange={(event) => setOutputRequirements(event.target.value)}
                placeholder="输出要求"
                size="small"
                style={{ width: 220 }}
              />
              <Select
                allowClear
                placeholder="PC 搜索账号"
                value={researchSearchAccountId ?? undefined}
                onChange={(value) => setResearchSearchAccountId(value ?? null)}
                size="small"
                style={{ minWidth: 180 }}
                options={pcAccounts.map((account) => ({
                  value: account.id,
                  label: accountLabel(account),
                }))}
              />
              <Space size={4}>
                <Text type="secondary" style={{ fontSize: 12 }}>保存</Text>
                <InputNumber
                  min={0}
                  max={10}
                  value={researchSearchLimit}
                  onChange={(value) => setResearchSearchLimit(value ?? 3)}
                  size="small"
                  style={{ width: 56 }}
                />
              </Space>
              <Checkbox
                checked={autoSaveResearch}
                onChange={(event) => setAutoSaveResearch(event.target.checked)}
                style={{ fontSize: 12 }}
              >
                入库
              </Checkbox>
            </Space>
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
    </>
  );
}
