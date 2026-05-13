# Agent 草稿生成 + 图片提示词自迭代设计

Date: 2026-05-13
Scope: 扩展 Agent 草稿生成流程，增加 topics 生成、12层图片提示词、自迭代质检闭环

## 1. 背景与目标

当前 `step=titles → step=draft → step=images` 三步流程过于简单：
- `step=titles` 仅返回标题列表
- `step=draft` 仅返回 body / tags / 简单 image_prompt
- `step=images` 直接调用生图 API，无质量控制

按照 `docs/agent-plan.md` 和 `docs/agent-loop.md`，需要：
1. `step=titles` 增加 topics 生成（3-5 个主题 + 推荐主题）
2. `step=draft` 增加封面策略、12层图片提示词 spec、发布建议
3. `step=images` 内部增加两轮迭代闭环：
   - **Prompt 自迭代**：Planner→Generator→Critic→Rewriter，最多 3 轮，目标分 4.5
   - **图片质检**：生图后 Vision Critic 检查，不合格则修正 prompt 重试，最多 2 次

## 2. Non-Goals

- 不改变前端三步流程的 UI 结构
- 不新增 API 端点
- 不修改现有 `/api/ai/generate-note` 等已有接口
- 不在数据库中持久化 image_prompt_spec（仅在内存中流转）

## 3. Service 层变更

文件：`backend/app/services/ai_service.py`

### 3.1 新增 Types / Data Classes

```python
class ImagePromptSpec(BaseModel):
    L1_publish_goal: str = ""
    L2_topic: str = ""
    L3_audience: str = ""
    L4_main_subject: str = ""
    L5_scene: str = ""
    L6_composition: str = ""
    L7_style: str = ""
    L8_color_lighting: str = ""
    L9_emotion: str = ""
    L10_details: str = ""
    L11_platform_adaptation: str = ""
    L12_negative_constraints: str = ""


class PromptQualityScore(BaseModel):
    theme_clarity: int = Field(ge=1, le=5)
    subject_clarity: int = Field(ge=1, le=5)
    composition_control: int = Field(ge=1, le=5)
    xiaohongshu_fit: int = Field(ge=1, le=5)
    style_consistency: int = Field(ge=1, le=5)
    negative_constraints: int = Field(ge=1, le=5)
    text_risk: int = Field(ge=1, le=5)  # 分数越高风险越低
    overall_score: float = Field(ge=1.0, le=5.0)


class ImageQualityCheck(BaseModel):
    is_relevant_to_topic: bool
    has_text_or_garbled_text: bool
    has_logo_or_watermark: bool
    has_qrcode: bool
    has_sensitive_content: bool
    has_deformed_face_or_hands: bool
    is_xiaohongshu_cover_ready: bool
    has_title_space: bool
    need_retry: bool
    retry_reason: str = ""


class IterationRound(BaseModel):
    iteration_round: int
    draft_prompt: str
    prompt_quality_score: PromptQualityScore
    failed_items: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)
    whether_need_rewrite: bool
    final_image_prompt: str
```

### 3.2 修改 `generate_draft_titles()`

**修改签名**：无（保持兼容）

**修改返回值**：

```python
# 旧返回值
list[str]  # ["标题1", "标题2", ...]

# 新返回值
{
    "titles": list[str],
    "recommended_title": str,
    "topics": list[str],        # 新增
    "recommended_topic": str,   # 新增
}
```

**内部逻辑**：
- 在 system prompt 中追加"生成 3-5 个小红书主题方向"
- 解析返回 JSON，提取 `topics` 和 `recommended_topic`
- 推荐主题由 AI 自选，或取 topics[0]

### 3.3 修改 `generate_single_draft()`

**修改签名**：无（保持兼容）

**修改返回值**：

```python
# 旧返回值
{
    "title": str,
    "body": str,
    "tags": list[str],
    "image_prompt": {
        "positive_prompt": str,
        "negative_prompt": str,
        "reference_strategy": str,
    }
}

# 新返回值
{
    "title": str,
    "body": str,
    "tags": list[str],
    "cover_strategy": {                          # 新增
        "cover_goal": str,
        "cover_type": str,
        "visual_core": str,
        "title_space": str,
        "text_in_image": bool,
    },
    "image_prompt_spec": ImagePromptSpec,        # 新增（12层）
    "publish_tips": str,                         # 新增
}
```

**内部逻辑**：
- 更新 system prompt，要求返回 12 层结构和封面策略
- 解析并验证 `image_prompt_spec` 12 层字段

### 3.4 新增 `iterate_image_prompt()`

```python
def iterate_image_prompt(
    image_prompt_spec: ImagePromptSpec,
    cover_strategy: dict,
    draft_body: str,
    reference_image_urls: list[str],
    model_config: ModelConfig,
    api_key: str,
    max_iterations: int = 3,
    target_score: float = 4.5,
) -> dict:
    """
    返回：
    {
        "final_image_prompt": str,
        "iteration_history": list[IterationRound],
        "total_rounds": int,
    }
    """
```

**内部流程**（对应 agent-loop.md 第5节 Planner/Generator/Critic/Rewriter 四节点）：

```
round = 1
while round <= max_iterations:
    1. Planner: 将 image_prompt_spec 格式化为结构化设计描述
    2. Generator: 基于结构化描述生成 draft_prompt
    3. Critic: 对 draft_prompt 评分（8维度）
    4. 如果 overall_score >= target_score 且 not whether_need_rewrite → break
    5. Rewriter: 根据 failed_items 改写 draft_prompt
    6. round += 1

final_image_prompt = last_draft_prompt
```

**评分维度**（对应 agent-plan.md 第10.1节）：
1. theme_clarity（主题清晰度）
2. subject_clarity（主体清晰度）
3. composition_control（构图可控性）
4. xiaohongshu_fit（小红书适配度）
5. style_consistency（风格一致性）
6. negative_constraints（禁止项完整度）
7. text_risk（文字风险，越高越好）
8. overall_score（综合评分，目标分 4.5，低于此分触发重写）

**Critic system prompt**（内联在方法中）：
```
你是一个小红书图片提示词质检员。请对以下生图提示词按8个维度评分（1-5分）。
评分维度：主题清晰度、主体清晰度、构图控制、小红书适配、风格一致性、禁止项完整性、文字风险、综合评分。
输出 JSON：{"scores": {...}, "overall_score": float, "failed_items": [], "improvement_suggestions": [], "whether_need_rewrite": bool}
如果 overall_score < 4.5 或存在关键失败项，whether_need_rewrite 必须为 true。
```

**Rewriter system prompt**：
```
你是一个小红书生图提示词改写专家。根据 Critic 的评分意见，重写 draft_prompt。
改写要求：
1. 保留原始主题和核心风格
2. 修复所有 failed_items
3. 增强 failed_items 指向的弱点
4. 输出：{"rewritten_prompt": str, "changes_made": [str]}
```

### 3.5 新增 `_check_generated_image_quality()`（私有辅助函数）

```python
def _check_generated_image_quality(
    image_url: str,
    topic: str,
    model_config: ModelConfig,
    api_key: str,
) -> ImageQualityCheck:
    """
    通过视觉语言模型（chat endpoint with vision）检查生成图片质量。
    返回 ImageQualityCheck 结构。供 generate_image_with_retry 内部调用。
    """
```

**内部逻辑**：
- 调用 `OpenAICompatibleImageClient.describe_image()` 但传入质检 prompt
- 解析返回的 JSON，映射到 `ImageQualityCheck` 字段

**质检 prompt**（内联）：
```
请检查以下小红书封面图片的质量，返回 JSON：
{
  "is_relevant_to_topic": bool,
  "has_text_or_garbled_text": bool,
  "has_logo_or_watermark": bool,
  "has_qrcode": bool,
  "has_sensitive_content": bool,
  "has_deformed_face_or_hands": bool,
  "is_xiaohongshu_cover_ready": bool,
  "has_title_space": bool,
  "need_retry": bool,
  "retry_reason": str
}
重点检查：乱码文字、Logo水印二维码、人物畸形、构图比例、标题留白。
```

### 3.6 图片级重试逻辑（生图后）

对应 agent-loop.md 第7节。生图并质检后：

```python
def generate_image_with_retry(
    final_image_prompt: str,
    reference_image_urls: list[str],
    image_model_config: ModelConfig,
    image_api_key: str,
    text_model_config: ModelConfig,
    text_api_key: str,
    draft_body: str,
    max_image_retries: int = 2,
) -> tuple[dict, ImageQualityCheck, list[IterationRound]]:
    """
    返回：(生图结果, 最终质检结果, 修正历史)
    """
```

**修正策略映射表**（agent-loop.md 第7节）：

| 质检问题 | 修正 prompt 追加内容 |
|---|---|
| has_text_or_garbled_text | +"不要生成任何文字、字母、数字、标牌、海报文字" |
| too_luxury_or_hotel_like | +"普通住宅尺度、2.7米层高、不要挑空、不要奢华大理石" |
| has_deformed_face_or_hands | +"人物脸部或手部不得变形，保持自然比例" |
| has_title_space == false | +"画面上方保留30%干净墙面留白" |
| composition issues | +"重新调整构图：主体居中或偏下，上方留白30%，背景干净" |

## 4. API 层变更

文件：`backend/app/api/ai.py`

### 4.1 `AgentDraftsChatRequest` 新增字段

```python
class AgentDraftsChatRequest(BaseModel):
    # ... 现有字段 ...
    # step=images 新增字段：
    cover_strategy: dict | None = None       # 来自 step=draft 响应
    image_prompt_spec: dict | None = None    # 来自 step=draft 响应
    draft_body: str | None = None            # 来自 step=draft 响应
    reference_image_urls: list[str] | None = None  # 从 messages 中提取
```

### 4.2 修改 `step=titles` 逻辑

- 解析 `generate_draft_titles()` 的新返回值
- 返回结构中增加 `topics` 和 `recommended_topic`

**Response 变化**：
```python
return _agent_drafts_response(task.id, payload.model, {
    "titles": titles,
    "recommended_title": recommended_title,
    "topics": topics,           # 新增
    "recommended_topic": recommended_topic,  # 新增
})
```

### 4.3 修改 `step=draft` 逻辑

- 解析 `generate_single_draft()` 的新返回值
- 返回结构中增加 `cover_strategy`、`image_prompt_spec`、`publish_tips`

**Response 变化**：
```python
return _agent_drafts_response(task.id, payload.model, {
    "draft": _serialize_draft(draft),
    "cover_strategy": draft_data.get("cover_strategy", {}),    # 新增
    "image_prompt_spec": draft_data.get("image_prompt_spec", {}),  # 新增
    "publish_tips": draft_data.get("publish_tips", ""),        # 新增
})
```

### 4.4 修改 `step=images` 逻辑

**旧流程**：
```
接收 draft_id + image_prompt → 直接生图 → 返回 assets
```

**新流程**：
```
接收 cover_strategy + image_prompt_spec + draft_body + reference_image_urls
  ↓
1. 构建 ImagePromptSpec 对象
2. 调用 text_ai_client.iterate_image_prompt()
   → final_image_prompt + iteration_history
  ↓
3. 调用 image_ai_client.generate_image() 生成图片
  ↓
4. 调用 _check_generated_image_quality() 检查图片
  ↓
5. 如果 need_retry：
     生成修正 prompt
     重发生图请求（最多2次）
     重新质检
  ↓
6. 保存 AiGeneratedAsset + DraftAsset
  ↓
返回 assets + iteration_history + final_image_prompt + image_quality_check
```

**Response 变化**：
```python
return _agent_drafts_response(task.id, payload.model, {
    "assets": item_assets,
    "iteration_history": iteration_history,    # 新增
    "final_image_prompt": final_image_prompt,   # 新增
    "image_quality_check": quality_check,       # 新增
    "errors": item_errors,
})
```

### 4.5 Error Handling

- `iterate_image_prompt` 超时或 LLM 格式错误：使用 `image_prompt_spec` 的 `L12_negative_constraints` 作为 fallback，直接拼接成 prompt
- `_check_generated_image_quality` 失败：默认 `need_retry = False`，记录 warning log
- 修正 prompt 生成失败：直接重试生图，不追加修正内容

## 5. 前端变更

### 5.1 Types（`frontend/src/types/index.ts`）

```typescript
// 扩展 AgentDraftItem
export interface CoverStrategy {
  cover_goal: string;
  cover_type: string;
  visual_core: string;
  title_space: string;
  text_in_image: boolean;
}

export interface ImagePromptSpec {
  L1_publish_goal: string;
  L2_topic: string;
  L3_audience: string;
  L4_main_subject: string;
  L5_scene: string;
  L6_composition: string;
  L7_style: string;
  L8_color_lighting: string;
  L9_emotion: string;
  L10_details: string;
  L11_platform_adaptation: string;
  L12_negative_constraints: string;
}

export interface PromptQualityScore {
  theme_clarity: number;
  subject_clarity: number;
  composition_control: number;
  xiaohongshu_fit: number;
  style_consistency: number;
  negative_constraints: number;
  text_risk: number;
  overall_score: number;
}

export interface IterationRound {
  iteration_round: number;
  draft_prompt: string;
  prompt_quality_score: PromptQualityScore;
  failed_items: string[];
  improvement_suggestions: string[];
  whether_need_rewrite: boolean;
  final_image_prompt: string;
}

export interface ImageQualityCheck {
  is_relevant_to_topic: boolean;
  has_text_or_garbled_text: boolean;
  has_logo_or_watermark: boolean;
  has_qrcode: boolean;
  has_sensitive_content: boolean;
  has_deformed_face_or_hands: boolean;
  is_xiaohongshu_cover_ready: boolean;
  has_title_space: boolean;
  need_retry: boolean;
  retry_reason: string;
}

export interface AgentDraftItem {
  // ... 现有字段 ...
  cover_strategy?: CoverStrategy;      // 新增
  image_prompt_spec?: ImagePromptSpec; // 新增
  publish_tips?: string;              // 新增
  iteration_history?: IterationRound[]; // 新增
  image_quality_check?: ImageQualityCheck; // 新增
}

// 扩展 AgentDraftPayload
export interface AgentDraftPayload {
  // ... 现有字段 ...
  cover_strategy?: CoverStrategy;
  image_prompt_spec?: ImagePromptSpec;
  draft_body?: string;
  reference_image_urls?: string[];
}

// 扩展 step 类型响应
export type { WorkflowStep } from "../components/ai/draft-step-card";

// 扩展 WorkflowStep 类型
export type EnhancedWorkflowStep =
  | { type: "titles"; status: "running" | "done" | "error"; titles?: string[]; topics?: string[]; recommended_topic?: string; recommended_title?: string; error?: string }
  | { type: "draft"; index: number; title: string; status: "running" | "done" | "error"; item?: AgentDraftItem; cover_strategy?: CoverStrategy; publish_tips?: string; error?: string }
  | { type: "images"; index: number; title: string; status: "running" | "done" | "error"; assets?: AgentDraftItem["assets"]; iteration_history?: IterationRound[]; image_quality_check?: ImageQualityCheck; error?: string };
```

### 5.2 System Prompt 更新（`use-draft-generation.ts`）

```typescript
const SYSTEM_PROMPT = `你是一个小红书内容策划与社群运营 Agent，擅长根据用户输入的文字需求和图片素材，生成适合小红书发布的完整笔记方案。

你的目标：
1. 理解用户的发布目的、目标人群、产品/活动/社群卖点。
2. 将用户需求拆解为小红书主题、标题、正文、标签、图片提示词。
3. 如果用户提供图片，需要结合图片内容进行分析和再创作。
4. 生成的小红书内容必须真实自然，避免生硬广告腔。
5. 文案要有小红书平台感，包括开头钩子、分段、emoji、痛点、收益、行动引导。
6. 图片提示词必须使用 12 层分层架构（L1-L12）。
7. 默认图片不直接生成文字，除非用户明确要求。
8. 不得生成违规、侵权、低俗、虚假承诺内容。
9. 输出内容需要结构化，方便后端调用生图模型。

工作流程：
- 第一步：分析输入需求和图片内容。
- 第二步：判断信息是否完整，如不完整，最多追问 3 个关键问题。
- 第三步：生成 3-5 个主题方向。
- 第四步：选择最适合的主题，生成 3-5 个标题。
- 第五步：生成完整小红书正文。
- 第六步：生成 8-12 个标签。
- 第七步：生成封面策略。
- 第八步：使用 12 层架构生成适合 gpt-image-2 的图片提示词。
- 第九步：对图片提示词进行质量评分。
- 第十步：调用生图工具生成图片。
- 第十一步：检查图片是否符合发布要求。
- 第十二步：输出最终小红书发布包。`;
```

### 5.3 Hook 修改（`use-draft-generation.ts`）

```typescript
// 每个 step 的 item 扩展为存储更多数据
interface ExtendedDraftItem extends AgentDraftItem {
  cover_strategy?: CoverStrategy;
  publish_tips?: string;
  image_prompt_spec?: ImagePromptSpec;
  iteration_history?: IterationRound[];
  image_quality_check?: ImageQualityCheck;
}
```

- `step=titles` 响应：提取 `topics`、`recommended_topic`，存入 step state
- `step=draft` 响应：提取 `cover_strategy`、`image_prompt_spec`、`publish_tips`，存入对应 draft step 的 item 中
- `step=images` 请求：携带 `cover_strategy`、`image_prompt_spec`、`draft_body`、`reference_image_urls`（从上一个 draft step 的 item 中读取）
- `step=images` 响应：提取 `iteration_history`、`image_quality_check`，存入对应 images step 的 item 中

### 5.4 UI 组件更新（`draft-step-card.tsx`）

**titles 步骤**：
```tsx
{step.type === "titles" && step.topics && (
  <Space direction="vertical" size={4} style={{ marginTop: 8 }}>
    <Text type="secondary" style={{ fontSize: 11 }}>推荐主题：{step.recommended_topic}</Text>
    {step.topics.map((t, i) => (
      <Tag key={i} color="purple" style={{ fontSize: 11 }}>{t}</Tag>
    ))}
  </Space>
)}
```

**draft 步骤**：
```tsx
{step.item?.cover_strategy && (
  <Alert
    message={<><Text type="secondary" style={{ fontSize: 11 }}>发布建议：</Text>{step.item.publish_tips}</>}
    type="info"
    style={{ fontSize: 11, marginTop: 6 }}
  />
)}
```

**images 步骤**：
```tsx
{step.iteration_history && step.iteration_history.length > 0 && (
  <Space direction="vertical" size={4} style={{ marginTop: 4 }}>
    {step.iteration_history.map((r, i) => (
      <Tag key={i} color={r.final_image_prompt === step.iteration_history![step.iteration_history!.length - 1].final_image_prompt ? "green" : "default"} style={{ fontSize: 11 }}>
        第{r.iteration_round}轮 分数:{r.prompt_quality_score.overall_score}
      </Tag>
    ))}
  </Space>
)}
{step.image_quality_check && (
  <Tag color={step.image_quality_check.need_retry ? "red" : "green"} style={{ fontSize: 11 }}>
    图片质检：{step.image_quality_check.need_retry ? step.image_quality_check.retry_reason : "通过"}
  </Tag>
)}
```

## 6. 测试用例

文件：`tests/backend/test_agent_drafts.py`

### 6.1 新增测试

```python
def test_iterate_image_prompt_converges_in_3_rounds():
    """Prompt 迭代在3轮内收敛到目标分。"""
    ...

def test_iterate_image_prompt_respects_max_iterations():
    """达到最大迭代次数后停止。"""
    ...

def test_iterate_image_prompt_rewriter_fixes_failed_items():
    """Rewriter 能修复 Critic 指出的 failed_items。"""
    ...

def test_check_image_quality_returns_structured_result():
    """图片质检返回完整的 ImageQualityCheck 结构。"""
    ...

def test_generate_image_with_retry_skips_retry_when_pass():
    """图片质检通过时不重试。"""
    ...

def test_generate_image_with_retry_retries_on_failure():
    """图片质检不通过时重试，最多2次。"""
    ...

def test_generate_draft_titles_returns_topics():
    """step=titles 返回 topics 和 recommended_topic。"""
    ...

def test_generate_single_draft_returns_12_layers():
    """step=draft 返回 12 层 image_prompt_spec。"""
    ...
```

## 7. 验收标准

- `step=titles` 响应包含 `topics`（3-5个）和 `recommended_topic`
- `step=draft` 响应包含 `cover_strategy`、`image_prompt_spec`（12层）、`publish_tips`
- `step=images` 内部完成 Prompt 自迭代（最多3轮），记录每轮评分
- `step=images` 内部完成图片质检，不合格时修正 prompt 重试（最多2次）
- 前端展示每轮迭代的评分和最终质检结果
- 后端测试覆盖新增逻辑
- 不影响现有 `generate-note`、`rewrite-note` 等已有接口
