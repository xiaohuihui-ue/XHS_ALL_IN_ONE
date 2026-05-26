import {
  CheckCircleOutlined,
  EyeOutlined,
  ExclamationCircleOutlined,
  LoadingOutlined,
} from "@ant-design/icons";
import { Alert, Button, Image, Space, Spin, Tag, Typography } from "antd";

import type {
  AgentDraftItem,
  CoverStrategy,
  ImagePromptSpec,
  IterationRound,
  ImageQualityCheck,
} from "../../types";

const { Text, Paragraph } = Typography;

export type TitlesStep = {
  type: "titles";
  status: "running" | "retrying" | "done" | "error";
  retryCount?: number;
  titles?: string[];
  recommended_title?: string;
  topics?: string[];
  recommended_topic?: string;
  error?: string;
};

export type DraftStep = {
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
};

export type ImagesStep = {
  type: "images";
  index: number;
  title: string;
  status: "running" | "retrying" | "done" | "error";
  draft_id?: number;
  retryCount?: number;
  assets?: AgentDraftItem["assets"];
  final_image_prompt?: string;
  iteration_history?: IterationRound[];
  image_quality_check?: ImageQualityCheck;
  errors?: string[];
  error?: string;
};

export type WorkflowStep = TitlesStep | DraftStep | ImagesStep;

function IterationBadge({ round }: { round: IterationRound }) {
  const score = round.prompt_quality_score.overall_score;
  const color = score >= 4.5 ? "green" : score >= 3.5 ? "orange" : "red";
  return (
    <Tag key={round.iteration_round} color={color} style={{ fontSize: 11 }}>
      第{round.iteration_round}轮 {score.toFixed(1)}分
    </Tag>
  );
}

export function DraftStepCard({ step }: { step: WorkflowStep }) {
  const isRunning = step.status === "running" || step.status === "retrying";
  const isRetrying = step.status === "retrying";
  const isError = step.status === "error";

  const label =
    step.type === "titles" ? "生成标题候选"
    : step.type === "draft" ? `草稿 ${step.index + 1}：${step.title}`
    : `生图 ${step.index + 1}：${step.title}`;

  const icon = isRunning
    ? <Spin indicator={<LoadingOutlined style={{ fontSize: 14 }} />} />
    : isError
    ? <ExclamationCircleOutlined style={{ color: "#ff4d4f", fontSize: 14 }} />
    : <CheckCircleOutlined style={{ color: "#52c41a", fontSize: 14 }} />;

  const hasContent =
    (step.type === "titles" && (step.titles?.length ?? 0) > 0) ||
    (step.type === "draft" && step.status === "done") ||
    (step.type === "images" && (step.assets?.length ?? 0) > 0);

  return (
    <div style={{
      width: "100%",
      marginBottom: 10,
      padding: "12px 16px",
      background: "var(--color-background-secondary)",
      borderRadius: 10,
      border: `1px solid ${isError ? "rgba(255,77,79,0.3)" : "var(--color-border)"}`,
    }}>
      <Space style={{ marginBottom: hasContent ? 8 : 0 }}>
        {icon}
        <Text style={{ fontSize: 13, fontWeight: 500 }}>{label}</Text>
        {isRetrying && (
          <Tag color="orange" style={{ fontSize: 11 }}>重试中 ({step.retryCount}/3)…</Tag>
        )}
        {step.type === "draft" && step.status === "done" && step.draft_id && (
          <Button
            size="small"
            type="link"
            icon={<EyeOutlined />}
            href={`/platforms/xhs/drafts/${step.draft_id}/preview`}
            target="_blank"
            style={{ height: 22, paddingInline: 0, fontSize: 12 }}
          >
            预览页
          </Button>
        )}
      </Space>

      {isError && (
        <Alert type="error" message={step.error} showIcon style={{ fontSize: 12, marginTop: 4 }} />
      )}

      {/* ── Titles step ── */}
      {step.type === "titles" && step.topics && step.topics.length > 0 && (
        <Space direction="vertical" size={4} style={{ marginTop: 8 }}>
          {step.recommended_topic && (
            <Text type="secondary" style={{ fontSize: 11 }}>
              推荐主题：{step.recommended_topic}
            </Text>
          )}
          <Space wrap>
            {step.topics.map((t, i) => (
              <Tag key={i} color="purple" style={{ fontSize: 11, margin: "2px 4px 2px 0" }}>{t}</Tag>
            ))}
          </Space>
        </Space>
      )}

      {step.type === "titles" && step.titles && step.titles.length > 0 && (
        <Space wrap style={{ marginTop: 4 }}>
          {step.titles.map((t, i) => (
            <Tag key={i} color="blue" style={{ fontSize: 12, margin: "2px 4px 2px 0" }}>{t}</Tag>
          ))}
        </Space>
      )}

      {/* ── Draft step ── */}
      {step.type === "draft" && step.status === "done" && (
        <div>
          {step.body && (
            <Paragraph
              ellipsis={{ rows: 3, expandable: true, symbol: "展开" }}
              style={{ fontSize: 12, color: "var(--color-text-secondary)", marginBottom: 8 }}
            >
              {step.body}
            </Paragraph>
          )}
          {step.tags && step.tags.length > 0 && (
            <Space wrap style={{ marginBottom: 6 }}>
              {step.tags.map((t) => (
                <Tag key={t.name} color="geekblue" style={{ fontSize: 11 }}>#{t.name}</Tag>
              ))}
            </Space>
          )}
          {step.publish_tips && (
            <Alert
              message={<Text type="secondary" style={{ fontSize: 11 }}>发布建议：{step.publish_tips}</Text>}
              type="info"
              style={{ fontSize: 11, marginBottom: 6 }}
            />
          )}
          {step.cover_strategy && (
            <div style={{ marginBottom: 6, padding: "6px 10px", background: "var(--color-background-elevated)", borderRadius: 6 }}>
              <Text type="secondary" style={{ fontSize: 11 }}>
                封面策略：{step.cover_strategy.cover_type} | 视觉核心：{step.cover_strategy.visual_core}
              </Text>
            </div>
          )}
        </div>
      )}

      {/* ── Images step ── */}
      {step.type === "images" && (
        <div>
          {/* Iteration history */}
          {step.iteration_history && step.iteration_history.length > 0 && (
            <Space wrap style={{ marginTop: 4 }}>
              {step.iteration_history.map((r) => (
                <IterationBadge key={r.iteration_round} round={r} />
              ))}
            </Space>
          )}

          {/* Image quality check */}
          {step.image_quality_check && (
            <div style={{ marginTop: 4 }}>
              {step.image_quality_check.need_retry ? (
                <Tag color="red" style={{ fontSize: 11 }}>
                  图片质检：需重试 — {step.image_quality_check.retry_reason || "质量问题"}
                </Tag>
              ) : (
                <Tag color="green" style={{ fontSize: 11 }}>图片质检：通过</Tag>
              )}
            </div>
          )}

          {/* Image previews */}
          {step.assets && step.assets.length > 0 ? (
            <Image.PreviewGroup>
              <Space wrap style={{ marginTop: 4 }}>
                {step.assets.map((a) => (
                  <Image
                    key={a.id}
                    src={a.url}
                    width={80}
                    height={80}
                    style={{ objectFit: "cover", borderRadius: 6 }}
                    referrerPolicy="no-referrer"
                    fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
                    placeholder={<Spin indicator={<LoadingOutlined />} style={{ lineHeight: "80px" }} />}
                  />
                ))}
              </Space>
            </Image.PreviewGroup>
          ) : step.type === "images" && step.status === "done" ? (
            <Text type="secondary" style={{ fontSize: 11, display: "block", marginTop: 4 }}>
              {(step as ImagesStep).errors && (step as ImagesStep).errors!.length > 0 ? (
                <span style={{ color: "#faad14" }}>{((step as ImagesStep).errors ?? []).join("；")}</span>
              ) : (
                <>暂无图片（{(step as ImagesStep).assets?.length ?? 0} 张）</>
              )}
            </Text>
          ) : step.type === "images" && (step.status === "running" || step.status === "retrying") ? (
            <Text type="secondary" style={{ fontSize: 11, display: "block", marginTop: 4 }}>
              正在生成图片…
            </Text>
          ) : null}
        </div>
      )}
    </div>
  );
}

