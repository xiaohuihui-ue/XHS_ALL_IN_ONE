import {
  CopyOutlined,
  DeleteOutlined,
  FileImageOutlined,
  FileTextOutlined,
  HomeOutlined,
  InboxOutlined,
  LinkOutlined,
  PictureOutlined,
  PlusOutlined,
  ReloadOutlined,
  RobotOutlined,
  StarOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Empty,
  Image,
  Input,
  InputNumber,
  message as antMessage,
  Modal,
  Row,
  Select,
  Space,
  Spin,
  Tabs,
  Tag,
  Typography,
  Upload,
} from "antd";
import { useEffect, useState } from "react";

import { PageHeader } from "../../../components/layout/app-shell";
import {
  deleteGeneratedImageAsset,
  deleteUserImage,
  describeImageWithAi,
  downloadExportFile,
  editImageWithAi,
  fetchExportFileText,
  fetchGeneratedImageAssets,
  fetchUserImages,
  generateImageWithAi,
  uploadAssetFile,
} from "../../../lib/api";
import { formatShanghaiTime } from "../../../lib/time";
import type { GeneratedImageAsset, UserImageFile } from "../../../types";
import {
  buildHomeDecorImageEditPayload,
  imageEditReportToPreview,
  imageEditArtifactToSummary,
} from "./image-edit-workflow";
import type { ImageEditArtifactSummary } from "./image-edit-workflow";

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

function isRenderableImage(value: string): boolean {
  return (
    value.startsWith("http://") ||
    value.startsWith("https://") ||
    value.startsWith("data:image/") ||
    value.startsWith("/api/")
  );
}

export function XhsImageStudioPage() {
  const [assets, setAssets] = useState<GeneratedImageAsset[]>([]);
  const [userImages, setUserImages] = useState<UserImageFile[]>([]);
  const [prompt, setPrompt] = useState("");
  const [referenceImages, setReferenceImages] = useState<string[]>([]);
  const [imageUrl, setImageUrl] = useState("");
  const [description, setDescription] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isDescribing, setIsDescribing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refPickerOpen, setRefPickerOpen] = useState(false);
  const [saveToAssets, setSaveToAssets] = useState(true);
  const [generatedPreview, setGeneratedPreview] = useState<string | null>(null);
  const [roomSourceImages, setRoomSourceImages] = useState<string[]>([]);
  const [roomEditIntent, setRoomEditIntent] = useState("生成一张现代奶油风小红书室内设计封面图，保留原始空间结构，提升软装质感和自然采光。");
  const [roomPreserveText, setRoomPreserveText] = useState("window position, ceiling height, room layout");
  const [roomChangeText, setRoomChangeText] = useState("sofa, wall color, lighting, decor");
  const [roomAvoidText, setRoomAvoidText] = useState("dark tones, text in image, watermark, distorted furniture");
  const [roomType, setRoomType] = useState("living_room");
  const [decorStyle, setDecorStyle] = useState("modern_cream");
  const [roomImageCount, setRoomImageCount] = useState(1);
  const [roomImageSize, setRoomImageSize] = useState("1024x1536");
  const [roomSaveToAssets, setRoomSaveToAssets] = useState(true);
  const [isEditingRoom, setIsEditingRoom] = useState(false);
  const [roomEditSummary, setRoomEditSummary] = useState<ImageEditArtifactSummary | null>(null);
  const [roomReportPreviewOpen, setRoomReportPreviewOpen] = useState(false);
  const [roomReportHtml, setRoomReportHtml] = useState("");
  const [isLoadingRoomReport, setIsLoadingRoomReport] = useState(false);

  // For the reference picker modal: which callback mode
  const [pickerMode, setPickerMode] = useState<"reference" | "describe" | "room_source">(
    "reference",
  );
  const [pickerUrlInput, setPickerUrlInput] = useState("");

  async function loadAssets() {
    setIsLoading(true);
    setError(null);
    try {
      const [aiResult, userResult] = await Promise.all([
        fetchGeneratedImageAssets(),
        fetchUserImages(),
      ]);
      setAssets(aiResult.items);
      setUserImages(userResult.items);
    } catch {
      setError("图片资产加载失败。");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleGenerate() {
    if (!prompt.trim()) {
      setError("请填写提示词。");
      return;
    }
    setIsGenerating(true);
    setError(null);
    setMessage(null);
    setGeneratedPreview(null);
    try {
      const result = await generateImageWithAi({
        prompt: prompt.trim(),
        reference_images:
          referenceImages.length > 0 ? referenceImages : undefined,
        save_to_assets: saveToAssets,
      });
      setGeneratedPreview(result.url);
      if (result.asset) {
        setAssets((prev) => [result.asset!, ...prev]);
      }
      setMessage("图片生成成功。");
    } catch {
      setError("AI 图片生成失败，请确认已配置图片生成模型。");
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleDescribeImage() {
    if (!imageUrl.trim()) {
      setError("请先填写图片 URL。");
      return;
    }
    setIsDescribing(true);
    setError(null);
    setMessage(null);
    try {
      const result = await describeImageWithAi({
        image_url: imageUrl.trim(),
        instruction: "提炼这张图片适合小红书发布的卖点、风格和标题方向。",
      });
      setDescription(result.text);
      setMessage("图片描述已生成。");
    } catch {
      setError("图片描述失败，请确认已配置支持视觉理解的图片模型。");
    } finally {
      setIsDescribing(false);
    }
  }

  async function handleRoomImageEdit() {
    if (roomSourceImages.length === 0) {
      setError("请先选择至少一张室内参考图。");
      return;
    }
    if (!roomEditIntent.trim()) {
      setError("请填写室内设计改造意图。");
      return;
    }

    setIsEditingRoom(true);
    setError(null);
    setMessage(null);
    setRoomEditSummary(null);
    setRoomReportHtml("");
    setRoomReportPreviewOpen(false);
    try {
      const payload = buildHomeDecorImageEditPayload({
        sourceImageUrls: roomSourceImages,
        editIntent: roomEditIntent,
        preserveText: roomPreserveText,
        changeText: roomChangeText,
        avoidText: roomAvoidText,
        roomType,
        decorStyle,
        imageCount: roomImageCount,
        size: roomImageSize,
        quality: "hd",
        style: "natural",
        responseFormat: "url",
        saveToAssets: roomSaveToAssets,
      });
      const artifact = await editImageWithAi(payload);
      setRoomEditSummary(imageEditArtifactToSummary(artifact));
      setMessage("室内设计图生图已完成，HTML 方案报告已生成。");
      if (roomSaveToAssets) {
        void loadAssets();
      }
    } catch {
      setError("室内设计图生图失败，请确认已配置图片生成模型。");
    } finally {
      setIsEditingRoom(false);
    }
  }

  async function handleDownloadRoomReport() {
    if (!roomEditSummary?.reportUrl || !roomEditSummary.reportFileName) return;
    try {
      await downloadExportFile(roomEditSummary.reportUrl, roomEditSummary.reportFileName);
    } catch {
      setError("HTML 方案报告下载失败，请重新登录后再试。");
    }
  }

  async function handlePreviewRoomReport() {
    const preview = roomEditSummary ? imageEditReportToPreview(roomEditSummary) : null;
    if (!preview) return;
    setRoomReportPreviewOpen(true);
    setIsLoadingRoomReport(true);
    setError(null);
    try {
      const html = await fetchExportFileText(preview.downloadUrl);
      setRoomReportHtml(html);
    } catch {
      setError("HTML 方案报告预览失败，请重新登录后再试。");
      setRoomReportPreviewOpen(false);
    } finally {
      setIsLoadingRoomReport(false);
    }
  }

  function openRefPicker(mode: "reference" | "describe" | "room_source") {
    setPickerMode(mode);
    setPickerUrlInput("");
    setRefPickerOpen(true);
  }

  function handlePickerSelect(url: string) {
    if (pickerMode === "reference") {
      setReferenceImages((prev) =>
        prev.includes(url) ? prev : [...prev, url],
      );
    } else if (pickerMode === "room_source") {
      setRoomSourceImages((prev) =>
        prev.includes(url) ? prev : [...prev, url],
      );
    } else {
      setImageUrl(url);
    }
    setRefPickerOpen(false);
  }

  function handlePickerUrlAdd() {
    const trimmed = pickerUrlInput.trim();
    if (!trimmed) return;
    handlePickerSelect(trimmed);
  }

  async function handleUploadFile(file: File) {
    try {
      const uploaded = await uploadAssetFile(file);
      const newItem: UserImageFile = {
        file_name: uploaded.file_name,
        url: uploaded.download_url,
        size: uploaded.size,
      };
      setUserImages((prev) => [newItem, ...prev]);
    } catch {
      setError("文件上传失败。");
    }
    return false; // prevent antd auto-upload
  }

  useEffect(() => {
    void loadAssets();
  }, []);

  const roomReportPreview = roomEditSummary ? imageEditReportToPreview(roomEditSummary) : null;

  return (
    <div>
      <PageHeader
        eyebrow="XHS Image Studio"
        title="图片工坊"
        description="AI 图片生成、图片描述、沉淀图片资产，赋能小红书内容创作。"
        action={
          <Button
            icon={<ReloadOutlined />}
            onClick={loadAssets}
            loading={isLoading}
          >
            刷新资产
          </Button>
        }
      />

      {error && (
        <Alert
          type="error"
          message={error}
          showIcon
          closable
          onClose={() => setError(null)}
          style={{ marginBottom: 16 }}
        />
      )}
      {message && (
        <Alert
          type="success"
          message={message}
          showIcon
          closable
          onClose={() => setMessage(null)}
          style={{ marginBottom: 16 }}
        />
      )}

      {/* ---- Top Row: Two tool cards ---- */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {/* Left Card: AI Image Generation */}
        <Col xs={24} md={14}>
          <Card
            title={
              <Space>
                <StarOutlined /> AI 图片生成
              </Space>
            }
            extra={
              <Text type="secondary" style={{ fontSize: 11 }}>
                需配置图片生成模型（如 gpt-image-2、豆包 Seedream）
              </Text>
            }
          >
            <TextArea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="充满活力的特写编辑肖像，模特眼神犀利，头戴雕塑感帽子，色彩拼接丰富，具有 Vogue 杂志封面的美学风格..."
              rows={4}
              disabled={isGenerating}
              style={{ marginBottom: 12 }}
            />

            {/* Reference images */}
            <div style={{ marginBottom: 12 }}>
              <Text
                type="secondary"
                style={{ fontSize: 12, marginBottom: 6, display: "block" }}
              >
                参考图
              </Text>
              <Space size={8} wrap>
                {referenceImages.map((url, idx) => (
                  <div
                    key={idx}
                    style={{
                      position: "relative",
                      width: 60,
                      height: 60,
                      borderRadius: 4,
                      overflow: "hidden",
                      border: "1px solid #333",
                    }}
                  >
                    {isRenderableImage(url) ? (
                      <img
                        src={url}
                        alt={`ref-${idx}`}
                        style={{
                          width: 60,
                          height: 60,
                          objectFit: "cover",
                        }}
                      />
                    ) : (
                      <div
                        style={{
                          width: 60,
                          height: 60,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          background: "#1a1a1a",
                        }}
                      >
                        <PictureOutlined style={{ fontSize: 20, color: "#666" }} />
                      </div>
                    )}
                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() =>
                        setReferenceImages((prev) =>
                          prev.filter((_, i) => i !== idx),
                        )
                      }
                      style={{
                        position: "absolute",
                        top: 0,
                        right: 0,
                        width: 18,
                        height: 18,
                        padding: 0,
                        minWidth: 18,
                        borderRadius: "0 4px 0 4px",
                        background: "rgba(0,0,0,0.6)",
                      }}
                    />
                  </div>
                ))}
                {/* Add placeholder */}
                <div
                  onClick={() => openRefPicker("reference")}
                  style={{
                    width: 60,
                    height: 60,
                    borderRadius: 4,
                    border: "1px dashed #444",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor: "pointer",
                    background: "#1a1a1a",
                  }}
                >
                  <PlusOutlined style={{ fontSize: 20, color: "#666" }} />
                </div>
              </Space>
            </div>

            {/* Controls row */}
            <Row
              justify="space-between"
              align="middle"
              style={{ marginBottom: 12 }}
            >
              <Col>
                <Checkbox
                  checked={saveToAssets}
                  onChange={(e) => setSaveToAssets(e.target.checked)}
                >
                  保存到 AI 图片资产
                </Checkbox>
              </Col>
              <Col>
                <Space>
                  <Button
                    onClick={() => { setPrompt(""); setReferenceImages([]); setGeneratedPreview(null); setSaveToAssets(true); }}
                    disabled={isGenerating}
                  >
                    重置
                  </Button>
                  <Button
                    type="primary"
                    icon={<RobotOutlined />}
                    onClick={handleGenerate}
                    loading={isGenerating}
                  >
                    生成
                  </Button>
                </Space>
              </Col>
            </Row>

            {/* Generated result */}
            {generatedPreview && (
              <div style={{ marginTop: 8 }}>
                <Text
                  type="secondary"
                  style={{ fontSize: 12, marginBottom: 6, display: "block" }}
                >
                  生成结果
                </Text>
                <div
                  style={{
                    background: "#1a1a1a",
                    borderRadius: 6,
                    padding: 8,
                    textAlign: "center",
                  }}
                >
                  <Image
                    src={generatedPreview}
                    alt="generated"
                    style={{ maxHeight: 240, objectFit: "contain" }}
                  />
                  {!saveToAssets && (
                    <Button
                      size="small"
                      type="link"
                      onClick={() => {
                        // Re-generate with save flag
                        setSaveToAssets(true);
                        setMessage("下次生成将自动保存到 AI 资产。");
                      }}
                      style={{ marginTop: 8 }}
                    >
                      保存到 AI 资产
                    </Button>
                  )}
                </div>
              </div>
            )}
          </Card>
        </Col>

        {/* Right Card: Image Description */}
        <Col xs={24} md={10}>
          <Card
            title={
              <Space>
                <FileImageOutlined /> 图片描述
              </Space>
            }
            extra={
              <Text type="secondary" style={{ fontSize: 11 }}>
                需配置多模态模型（如 GPT-4o）
              </Text>
            }
          >
            <Space.Compact style={{ width: "100%", marginBottom: 12 }}>
              <Input
                value={imageUrl}
                onChange={(e) => setImageUrl(e.target.value)}
                placeholder="图片 URL"
                disabled={isGenerating}
              />
              <Button
                icon={<PictureOutlined />}
                onClick={() => openRefPicker("describe")}
              >
                从资产选择
              </Button>
            </Space.Compact>
            <Button
              onClick={handleDescribeImage}
              loading={isDescribing}
              block
              style={{ marginBottom: 12 }}
            >
              生成描述
            </Button>
            {description && (
              <Paragraph
                style={{
                  background: "#262626",
                  padding: 12,
                  borderRadius: 6,
                  fontSize: 13,
                  margin: 0,
                }}
              >
                {description}
              </Paragraph>
            )}
          </Card>
        </Col>
      </Row>

      <Card
        title={
          <Space>
            <HomeOutlined /> 室内设计图生图
          </Space>
        }
        extra={
          <Text type="secondary" style={{ fontSize: 11 }}>
            输出结构化 artifact 和 HTML 方案报告
          </Text>
        }
        style={{ marginBottom: 24 }}
      >
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={10}>
            <Space direction="vertical" size={10} style={{ width: "100%" }}>
              <Text type="secondary" style={{ fontSize: 12 }}>源图 / 参考图</Text>
              <Space size={8} wrap>
                {roomSourceImages.map((url, index) => (
                  <div
                    key={url}
                    style={{
                      position: "relative",
                      width: 78,
                      height: 78,
                      borderRadius: 6,
                      overflow: "hidden",
                      border: "1px solid #333",
                      background: "#1a1a1a",
                    }}
                  >
                    {isRenderableImage(url) ? (
                      <img
                        src={url}
                        alt={`room-source-${index + 1}`}
                        style={{ width: 78, height: 78, objectFit: "cover" }}
                      />
                    ) : (
                      <PictureOutlined style={{ fontSize: 22, color: "#666", margin: 28 }} />
                    )}
                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => setRoomSourceImages((prev) => prev.filter((item) => item !== url))}
                      style={{
                        position: "absolute",
                        top: 0,
                        right: 0,
                        width: 20,
                        height: 20,
                        minWidth: 20,
                        padding: 0,
                        background: "rgba(0,0,0,0.6)",
                      }}
                    />
                  </div>
                ))}
                <Button
                  icon={<PlusOutlined />}
                  onClick={() => openRefPicker("room_source")}
                  style={{ width: 78, height: 78 }}
                />
              </Space>
              <TextArea
                value={roomEditIntent}
                onChange={(e) => setRoomEditIntent(e.target.value)}
                rows={4}
                placeholder="描述希望生成的室内设计效果"
                disabled={isEditingRoom}
              />
            </Space>
          </Col>

          <Col xs={24} lg={14}>
            <Row gutter={[12, 12]}>
              <Col xs={24} md={8}>
                <Text type="secondary" style={{ fontSize: 12 }}>保留</Text>
                <Input
                  value={roomPreserveText}
                  onChange={(e) => setRoomPreserveText(e.target.value)}
                  disabled={isEditingRoom}
                />
              </Col>
              <Col xs={24} md={8}>
                <Text type="secondary" style={{ fontSize: 12 }}>改变</Text>
                <Input
                  value={roomChangeText}
                  onChange={(e) => setRoomChangeText(e.target.value)}
                  disabled={isEditingRoom}
                />
              </Col>
              <Col xs={24} md={8}>
                <Text type="secondary" style={{ fontSize: 12 }}>避免</Text>
                <Input
                  value={roomAvoidText}
                  onChange={(e) => setRoomAvoidText(e.target.value)}
                  disabled={isEditingRoom}
                />
              </Col>
              <Col xs={12} md={6}>
                <Text type="secondary" style={{ fontSize: 12 }}>房间</Text>
                <Select
                  value={roomType}
                  onChange={setRoomType}
                  disabled={isEditingRoom}
                  style={{ width: "100%" }}
                  options={[
                    { value: "living_room", label: "客厅" },
                    { value: "bedroom", label: "卧室" },
                    { value: "dining_room", label: "餐厅" },
                    { value: "study", label: "书房" },
                    { value: "kitchen", label: "厨房" },
                  ]}
                />
              </Col>
              <Col xs={12} md={6}>
                <Text type="secondary" style={{ fontSize: 12 }}>风格</Text>
                <Select
                  value={decorStyle}
                  onChange={setDecorStyle}
                  disabled={isEditingRoom}
                  style={{ width: "100%" }}
                  options={[
                    { value: "modern_cream", label: "现代奶油风" },
                    { value: "japandi", label: "侘寂原木" },
                    { value: "light_luxury", label: "轻奢" },
                    { value: "minimalist", label: "极简" },
                    { value: "french_vintage", label: "法式复古" },
                  ]}
                />
              </Col>
              <Col xs={12} md={4}>
                <Text type="secondary" style={{ fontSize: 12 }}>数量</Text>
                <InputNumber
                  min={1}
                  max={4}
                  value={roomImageCount}
                  onChange={(value) => setRoomImageCount(value ?? 1)}
                  disabled={isEditingRoom}
                  style={{ width: "100%" }}
                />
              </Col>
              <Col xs={12} md={4}>
                <Text type="secondary" style={{ fontSize: 12 }}>尺寸</Text>
                <Select
                  value={roomImageSize}
                  onChange={setRoomImageSize}
                  disabled={isEditingRoom}
                  style={{ width: "100%" }}
                  options={[
                    { value: "1024x1536", label: "1024x1536" },
                    { value: "1024x1024", label: "1024x1024" },
                    { value: "1792x1024", label: "1792x1024" },
                  ]}
                />
              </Col>
              <Col xs={24} md={4} style={{ display: "flex", alignItems: "end" }}>
                <Checkbox
                  checked={roomSaveToAssets}
                  onChange={(e) => setRoomSaveToAssets(e.target.checked)}
                  disabled={isEditingRoom}
                >
                  入库
                </Checkbox>
              </Col>
            </Row>

            <Space wrap style={{ marginTop: 12 }}>
              <Button
                type="primary"
                icon={<RobotOutlined />}
                loading={isEditingRoom}
                onClick={handleRoomImageEdit}
              >
                生成室内设计图
              </Button>
              {roomEditSummary?.reportUrl && roomEditSummary.reportFileName && (
                <>
                  <Button icon={<FileTextOutlined />} onClick={() => void handlePreviewRoomReport()}>
                    预览 HTML 方案报告
                  </Button>
                  <Button icon={<FileImageOutlined />} onClick={() => void handleDownloadRoomReport()}>
                    下载 HTML 方案报告
                  </Button>
                </>
              )}
              {roomEditSummary?.knowledgeBase && (
                <Tag color="blue">{roomEditSummary.knowledgeBase}</Tag>
              )}
              {roomEditSummary?.passed !== undefined && (
                <Tag color={roomEditSummary.passed ? "green" : "orange"}>
                  质量检查{roomEditSummary.passed ? "通过" : "需复核"}
                </Tag>
              )}
            </Space>

            {roomEditSummary && (
              <div style={{ marginTop: 12 }}>
                {roomEditSummary.failedOrWarningChecks.length > 0 && (
                  <Alert
                    type="warning"
                    showIcon
                    message={`需复核：${roomEditSummary.failedOrWarningChecks.join("、")}`}
                    style={{ marginBottom: 10 }}
                  />
                )}
                <Image.PreviewGroup>
                  <Space wrap>
                    {roomEditSummary.resultUrls.map((url, index) => (
                      <Image
                        key={`${url}-${index}`}
                        src={url}
                        width={120}
                        height={120}
                        style={{ objectFit: "cover", borderRadius: 6 }}
                      />
                    ))}
                  </Space>
                </Image.PreviewGroup>
                {roomEditSummary.positivePrompt && (
                  <Paragraph
                    ellipsis={{ rows: 3, expandable: true, symbol: "展开" }}
                    style={{ marginTop: 10, marginBottom: 0, fontSize: 12 }}
                  >
                    {roomEditSummary.positivePrompt}
                  </Paragraph>
                )}
              </div>
            )}
          </Col>
        </Row>
      </Card>

      {/* ---- Bottom: Tabs ---- */}
      <Tabs
        defaultActiveKey="ai_assets"
        items={[
          {
            key: "ai_assets",
            label: (
              <Space>
                <StarOutlined /> AI 图片资产
              </Space>
            ),
            children: (
              <>
                {isLoading ? (
                  <div style={{ textAlign: "center", padding: 48 }}>
                    <Spin tip="正在加载 AI 图片资产..." />
                  </div>
                ) : assets.length === 0 ? (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="暂无 AI 图片资产。"
                    style={{ padding: 32 }}
                  />
                ) : (
                  <Row gutter={[12, 12]}>
                    {assets.map((asset) => (
                      <Col xs={12} sm={8} md={6} key={asset.id}>
                        <Card
                          size="small"
                          hoverable
                          styles={{ body: { padding: 8 } }}
                        >
                          <div
                            style={{
                              height: 120,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              marginBottom: 6,
                              overflow: "hidden",
                              borderRadius: 4,
                              background: "#1a1a1a",
                            }}
                          >
                            {isRenderableImage(asset.file_path) ? (
                              <Image
                                alt={asset.prompt}
                                src={asset.file_path}
                                style={{
                                  maxHeight: 120,
                                  objectFit: "contain",
                                }}
                              />
                            ) : (
                              <PictureOutlined
                                style={{ fontSize: 28, color: "#555" }}
                              />
                            )}
                          </div>
                          <Text
                            strong
                            ellipsis
                            style={{ fontSize: 12, display: "block" }}
                          >
                            {asset.prompt}
                          </Text>
                          <div style={{ marginTop: 4 }}>
                            <Tag
                              style={{
                                fontSize: 10,
                                padding: "0 4px",
                                margin: 0,
                              }}
                            >
                              {asset.model_name || "image model"}
                            </Tag>
                            <Text
                              type="secondary"
                              style={{ fontSize: 10, marginLeft: 4 }}
                            >
                              {formatShanghaiTime(asset.created_at)}
                            </Text>
                          </div>
                          <div style={{ display: "flex", gap: 4, marginTop: 4 }}>
                            <Button
                              type="text" size="small" icon={<CopyOutlined />}
                              onClick={() => {
                                navigator.clipboard.writeText(asset.prompt);
                                antMessage.success("提示词已复制");
                              }}
                              style={{ flex: 1 }}
                            >
                              提示词
                            </Button>
                            <Button
                              type="text" size="small" icon={<CopyOutlined />}
                              onClick={async () => {
                                if (!isRenderableImage(asset.file_path)) {
                                  antMessage.warning("图片不可用");
                                  return;
                                }
                                try {
                                  const resp = await fetch(asset.file_path);
                                  const blob = await resp.blob();
                                  await navigator.clipboard.write([
                                    new ClipboardItem({ [blob.type]: blob }),
                                  ]);
                                  antMessage.success("图片已复制");
                                } catch {
                                  antMessage.error("复制图片失败");
                                }
                              }}
                              style={{ flex: 1 }}
                            >
                              图片
                            </Button>
                          </div>
                          <Button
                            type="text" danger size="small" icon={<DeleteOutlined />}
                            onClick={async () => {
                              try {
                                await deleteGeneratedImageAsset(asset.id);
                                setAssets((prev) => prev.filter((a) => a.id !== asset.id));
                              } catch { /* global interceptor shows error */ }
                            }}
                            style={{ width: "100%", marginTop: 4 }}
                          >
                            删除
                          </Button>
                        </Card>
                      </Col>
                    ))}
                  </Row>
                )}
              </>
            ),
          },
          {
            key: "user_images",
            label: (
              <Space>
                <PictureOutlined /> 普通图片资产
              </Space>
            ),
            children: (
              <>
                <div style={{ marginBottom: 16 }}>
                  <Upload
                    accept="image/*"
                    showUploadList={false}
                    beforeUpload={(file) => {
                      void handleUploadFile(file);
                      return false;
                    }}
                  >
                    <Button icon={<UploadOutlined />}>上传图片</Button>
                  </Upload>
                </div>
                {userImages.length === 0 ? (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="暂无普通图片资产。上传图片后将显示在这里。"
                    style={{ padding: 32 }}
                  />
                ) : (
                  <Row gutter={[12, 12]}>
                    {userImages.map((img) => (
                      <Col xs={12} sm={8} md={6} key={img.file_name}>
                        <Card
                          size="small"
                          hoverable
                          styles={{ body: { padding: 8 } }}
                        >
                          <div
                            style={{
                              height: 120,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              marginBottom: 6,
                              overflow: "hidden",
                              borderRadius: 4,
                              background: "#1a1a1a",
                            }}
                          >
                            <Image
                              alt={img.file_name}
                              src={img.url}
                              style={{
                                maxHeight: 120,
                                objectFit: "contain",
                              }}
                            />
                          </div>
                          <Text
                            strong
                            ellipsis
                            style={{ fontSize: 12, display: "block" }}
                          >
                            {img.file_name}
                          </Text>
                          <Text type="secondary" style={{ fontSize: 10 }}>
                            {(img.size / 1024).toFixed(1)} KB
                          </Text>
                          <Button
                            type="text" danger size="small" icon={<DeleteOutlined />}
                            onClick={async () => {
                              try {
                                await deleteUserImage(img.file_name);
                                setUserImages((prev) => prev.filter((i) => i.file_name !== img.file_name));
                              } catch { /* global interceptor shows error */ }
                            }}
                            style={{ width: "100%", marginTop: 4 }}
                          >
                            删除
                          </Button>
                        </Card>
                      </Col>
                    ))}
                  </Row>
                )}
              </>
            ),
          },
        ]}
      />

      <Modal
        title={roomReportPreview?.title || "HTML 方案报告预览"}
        open={roomReportPreviewOpen}
        onCancel={() => setRoomReportPreviewOpen(false)}
        footer={
          roomReportPreview ? (
            <Space>
              <Button onClick={() => setRoomReportPreviewOpen(false)}>关闭</Button>
              <Button
                type="primary"
                icon={<FileImageOutlined />}
                onClick={() => void handleDownloadRoomReport()}
              >
                下载 HTML 方案报告
              </Button>
            </Space>
          ) : null
        }
        width="86vw"
        destroyOnClose
      >
        {isLoadingRoomReport ? (
          <div style={{ height: "70vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Spin tip="正在加载 HTML 方案报告..." />
          </div>
        ) : (
          <iframe
            title={roomReportPreview?.title || "HTML 方案报告预览"}
            srcDoc={roomReportHtml}
            sandbox=""
            style={{
              width: "100%",
              height: "70vh",
              border: "1px solid rgba(255,255,255,0.12)",
              borderRadius: 8,
              background: "#fff",
            }}
          />
        )}
      </Modal>

      {/* ---- Reference Image Picker Modal ---- */}
      <Modal
        title="选择图片"
        open={refPickerOpen}
        onCancel={() => setRefPickerOpen(false)}
        footer={null}
        width={640}
        destroyOnClose
      >
        <Tabs
          defaultActiveKey="user_images"
          items={[
            {
              key: "user_images",
              label: (
                <Space>
                  <PictureOutlined /> 普通图片资产
                </Space>
              ),
              children:
                userImages.length === 0 ? (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="暂无普通图片资产。"
                    style={{ padding: 24 }}
                  />
                ) : (
                  <Row gutter={[8, 8]}>
                    {userImages.map((img) => (
                      <Col span={6} key={img.file_name}>
                        <div
                          onClick={() => handlePickerSelect(img.url)}
                          style={{
                            cursor: "pointer",
                            borderRadius: 4,
                            overflow: "hidden",
                            border: "1px solid #333",
                            height: 240,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            background: "#1a1a1a",
                          }}
                        >
                          <img
                            src={img.url}
                            alt={img.file_name}
                            style={{
                              maxHeight: 240,
                              maxWidth: "100%",
                              objectFit: "contain",
                            }}
                          />
                        </div>
                      </Col>
                    ))}
                  </Row>
                ),
            },
            {
              key: "ai_assets",
              label: (
                <Space>
                  <StarOutlined /> AI 图片资产
                </Space>
              ),
              children:
                assets.length === 0 ? (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="暂无 AI 图片资产。"
                    style={{ padding: 24 }}
                  />
                ) : (
                  <Row gutter={[8, 8]}>
                    {assets.map((asset) => (
                      <Col span={6} key={asset.id}>
                        <div
                          onClick={() => handlePickerSelect(asset.file_path)}
                          style={{
                            cursor: "pointer",
                            borderRadius: 4,
                            overflow: "hidden",
                            border: "1px solid #333",
                            height: 240,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            background: "#1a1a1a",
                          }}
                        >
                          {isRenderableImage(asset.file_path) ? (
                            <img
                              src={asset.file_path}
                              alt={asset.prompt}
                              style={{
                                maxHeight: 240,
                                maxWidth: "100%",
                                objectFit: "contain",
                              }}
                            />
                          ) : (
                            <PictureOutlined
                              style={{ fontSize: 24, color: "#555" }}
                            />
                          )}
                        </div>
                      </Col>
                    ))}
                  </Row>
                ),
            },
            {
              key: "url",
              label: (
                <Space>
                  <LinkOutlined /> URL
                </Space>
              ),
              children: (
                <Space.Compact style={{ width: "100%" }}>
                  <Input
                    value={pickerUrlInput}
                    onChange={(e) => setPickerUrlInput(e.target.value)}
                    placeholder="输入图片 URL"
                    onPressEnter={handlePickerUrlAdd}
                  />
                  <Button type="primary" onClick={handlePickerUrlAdd}>
                    添加
                  </Button>
                </Space.Compact>
              ),
            },
          ]}
        />
      </Modal>
    </div>
  );
}
