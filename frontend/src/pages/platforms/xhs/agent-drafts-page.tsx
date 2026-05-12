import {
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  LoadingOutlined,
  PictureOutlined,
  RobotOutlined,
  SendOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Form,
  Image,
  Input,
  InputNumber,
  Row,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import { useState } from "react";

import { PageHeader } from "../../../components/layout/app-shell";
import { generateAgentDrafts } from "../../../lib/api";
import type { AgentDraftBatchResult, AgentDraftItem } from "../../../types";

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

function DraftResultCard({ item }: { item: AgentDraftItem }) {
  const statusIcon =
    item.status === "completed" ? (
      <CheckCircleOutlined style={{ color: "#52c41a" }} />
    ) : item.status === "partial" ? (
      <ExclamationCircleOutlined style={{ color: "#faad14" }} />
    ) : (
      <ExclamationCircleOutlined style={{ color: "#ff4d4f" }} />
    );

  return (
    <Card
      size="small"
      title={
        <Space>
          {statusIcon}
          <Text strong style={{ fontSize: 13 }}>
            {item.draft.title || "（无标题）"}
          </Text>
          <Badge
            count={`草稿 #${item.draft.id}`}
            style={{ background: "#1668dc", fontSize: 11 }}
          />
        </Space>
      }
      style={{ marginBottom: 12 }}
    >
      <Paragraph
        ellipsis={{ rows: 3, expandable: true, symbol: "展开" }}
        style={{ fontSize: 12, color: "rgba(255,255,255,0.75)" }}
      >
        {item.draft.body}
      </Paragraph>
      {item.draft.tags.length > 0 && (
        <Space wrap style={{ marginBottom: 8 }}>
          {item.draft.tags.map((t) => (
            <Tag key={t.name} color="blue" style={{ fontSize: 11 }}>
              #{t.name}
            </Tag>
          ))}
        </Space>
      )}
      {item.assets.length > 0 && (
        <Image.PreviewGroup>
          <Space wrap>
            {item.assets.map((a) => (
              <Image
                key={a.id}
                src={a.url}
                width={80}
                height={80}
                style={{ objectFit: "cover", borderRadius: 4 }}
                placeholder={
                  <Spin
                    indicator={<LoadingOutlined />}
                    style={{ lineHeight: "80px" }}
                  />
                }
              />
            ))}
          </Space>
        </Image.PreviewGroup>
      )}
      {item.errors.length > 0 && (
        <Alert
          type="warning"
          style={{ marginTop: 8, fontSize: 11 }}
          message={item.errors.join("; ")}
          showIcon
        />
      )}
    </Card>
  );
}

export function XhsAgentDraftsPage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AgentDraftBatchResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [form] = Form.useForm<{
    request: string;
    n: number;
    images_per_draft: number;
    output_requirements: string;
  }>();

  const handleGenerate = async () => {
    const values = await form.validateFields();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await generateAgentDrafts({
        messages: [
          {
            role: "system",
            content:
              "You are a Xiaohongshu content strategist and visual prompt engineer. Generate publish-ready XHS draft candidates.",
          },
          { role: "user", content: values.request },
        ],
        n: values.n,
        metadata: {
          platform: "xhs",
          output_requirements: values.output_requirements || undefined,
        },
        image_options: { n: values.images_per_draft },
      });
      setResult(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="XHS · AI"
        title="Agent 草稿生成"
        description="描述内容需求，一次生成多篇可发布的小红书草稿及配套图片。"
      />

      <Row gutter={24}>
        <Col xs={24} lg={10}>
          <Card title="生成设置" size="small" style={{ marginBottom: 16 }}>
            <Form
              form={form}
              layout="vertical"
              initialValues={{ n: 3, images_per_draft: 1, request: "", output_requirements: "" }}
            >
              <Form.Item
                name="request"
                label="内容需求"
                rules={[{ required: true, message: "请描述内容需求" }]}
              >
                <TextArea
                  rows={5}
                  placeholder="例如：生成3篇低卡早餐种草笔记，受众是减脂人群，语气自然亲切，附带图片提示词。"
                  maxLength={2000}
                  showCount
                />
              </Form.Item>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item name="n" label="草稿数量">
                    <InputNumber min={1} max={10} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="images_per_draft" label="每篇图片数">
                    <InputNumber min={0} max={3} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item name="output_requirements" label="输出要求（可选）">
                <Input placeholder="例如：每篇必须包含3个标签，突出卖点" maxLength={500} />
              </Form.Item>
              <Form.Item>
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  loading={loading}
                  onClick={() => void handleGenerate()}
                  block
                >
                  开始生成
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        <Col xs={24} lg={14}>
          {loading && (
            <div style={{ textAlign: "center", padding: "48px 0" }}>
              <Spin
                indicator={<LoadingOutlined style={{ fontSize: 32 }} />}
                tip="正在生成草稿…"
              />
            </div>
          )}
          {error && (
            <Alert type="error" message="生成失败" description={error} showIcon style={{ marginBottom: 16 }} />
          )}
          {result && !loading && (
            <>
              <Space style={{ marginBottom: 12 }}>
                <RobotOutlined />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  生成完成：{result.created_count} 篇草稿，{result.failed_count} 篇失败
                </Text>
              </Space>
              {result.items.map((item, i) => (
                <DraftResultCard key={item.draft.id ?? i} item={item} />
              ))}
            </>
          )}
          {!loading && !error && !result && (
            <div style={{ textAlign: "center", padding: "64px 0", color: "rgba(255,255,255,0.25)" }}>
              <PictureOutlined style={{ fontSize: 40, marginBottom: 12, display: "block" }} />
              <Text type="secondary">填写左侧设置后点击「开始生成」</Text>
            </div>
          )}
        </Col>
      </Row>
    </>
  );
}
