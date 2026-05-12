# Image Edit Spec — 图生图规范化设计

**日期：** 2026-05-11  
**范围：** Schema 定义（方案 A，仅规范，不改动现有代码）  
**目标文件：** `backend/app/schemas/image_edit.py`

---

## 背景

现有图生图接口（`POST /ai/images/generate`）以自然语言 `prompt` + `reference_images` 列表为输入，返回 `{"url": ..., "raw": ..., "asset": ...}`。这种设计导致：

- 输入不可控：prompt 质量完全依赖调用方
- 输出无契约：返回 `dict[str, Any]`，调用方无法静态感知结构
- 流程不可审查：生成过程是黑盒，无中间状态可观测

本设计将图生图从"生成一张图"升级为"执行一个有输入契约、有中间计划、有输出 artifact、有质量检查、有可追溯元数据的图片生成任务"。

---

## 设计原则

- **接口契约优先**：所有层围绕 `ImageEditSpec` 而非自然语言 prompt
- **渐进填充**：`ImageGenerationArtifact` 贯穿流水线生命周期，字段随流程推进逐步填入
- **不可变完成态**：`status=completed` 后 Artifact 冻结，重新生成创建新 Artifact
- **向后兼容**：旧接口 `POST /ai/images/generate` 不改动，新接口 `POST /ai/images/edit` 使用新 schema

---

## 文件布局

```
backend/app/schemas/
└── image_edit.py    ← 所有层的 Pydantic 模型
```

---

## 枚举类型

```python
class TaskType(str, Enum):
    style_transfer    = "style_transfer"     # 风格转换（必须保留结构）
    room_makeover     = "room_makeover"      # 空间改造（允许较大改动）
    material_replace  = "material_replace"   # 材质替换
    lighting_enhance  = "lighting_enhance"   # 光线增强
    declutter         = "declutter"          # 去杂物/整理空间
    cover_composition = "cover_composition"  # 小红书封面构图（预留标题区）
    detail_enhance    = "detail_enhance"     # 局部细节增强
    variation         = "variation"          # 同风格多版本变体

class Domain(str, Enum):
    home_decor = "home_decor"
    general    = "general"

class OutputGoal(str, Enum):
    xhs_cover = "xhs_cover"
    xhs_body  = "xhs_body"
    general   = "general"

class RealismLevel(str, Enum):
    low    = "low"
    medium = "medium"
    high   = "high"

class ArtifactStatus(str, Enum):
    pending    = "pending"
    planning   = "planning"
    generating = "generating"
    reviewing  = "reviewing"
    completed  = "completed"
    failed     = "failed"

class CheckStatus(str, Enum):
    pass_   = "pass"
    warning = "warning"
    fail    = "fail"
    skipped = "skipped"
```

---

## 五层模型

### 第 1 层：ImageEditSpec（结构化输入）

```python
class SourceImage(BaseModel):
    id: str
    role: str        # e.g. "reference_room", "style_ref"
    url: str

class ImageEditSpec(BaseModel):
    source_images: list[SourceImage]
    task_type: TaskType
    domain: Domain = Domain.general
    edit_intent: str = Field(min_length=1, max_length=500)
    preserve: list[str] = Field(default_factory=list)
    change: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    output_goal: OutputGoal = OutputGoal.general
    realism_level: RealismLevel = RealismLevel.high
    # domain=home_decor 时的可选字段
    room_type: str | None = None
    decor_style: str | None = None
```

**约定：**
- `preserve`/`change`/`avoid` 是人类可读的约束列表，后续 prompt 编译器将其转换为 positive/negative prompt
- `task_type` 决定默认的 preserve/change 规则（如 `style_transfer` 默认保留结构，`room_makeover` 允许较大改动）

---

### 第 2 层：EditPlan（编辑计划）

```python
class EditStep(BaseModel):
    step: int
    name: str
    instruction: str

class EditPlan(BaseModel):
    layout_policy: str
    style_policy: str
    material_policy: str
    lighting_policy: str
    composition_policy: str
    steps: list[EditStep]
```

**约定：**
- EditPlan 是生成前的可审查中间层，让系统先产出"编辑计划"再生成图片
- 每个 policy 字段是一句话描述，对应 spec 中的约束维度

---

### 第 3 层：CompiledPrompts（编译后的 prompt）

```python
class CompiledPrompts(BaseModel):
    positive_prompt: str
    negative_prompt: str
    compiler_version: str = "image_prompt_compiler_v1"
```

**约定：**
- 由 prompt 编译器从 `ImageEditSpec` + `EditPlan` 生成，不由用户直接填写
- `compiler_version` 用于追溯 prompt 生成逻辑版本

---

### 第 4 层：GenerationResult（原始生成结果）

```python
class ResultAsset(BaseModel):
    url: str
    width: int | None = None
    height: int | None = None

class GenerationResult(BaseModel):
    assets: list[ResultAsset]
    raw_response: dict[str, Any] | None = None
```

---

### 第 5 层：QualityReport（质量检查）

```python
class QualityCheckItem(BaseModel):
    name: str
    status: CheckStatus
    message: str

class QualityReport(BaseModel):
    passed: bool
    checks: list[QualityCheckItem]
```

**home_decor 域标准检查项（常量，不放进模型）：**

```python
HOME_DECOR_CHECK_NAMES: tuple[str, ...] = (
    "structure_preserved",       # 是否保留原图空间结构
    "style_applied",             # 是否应用目标风格
    "material_realism",          # 材质是否真实
    "lighting_consistency",      # 光线是否一致
    "furniture_geometry",        # 家具比例和透视是否合理
    "home_decor_expressiveness", # 是否有家装表现力
    "xhs_cover_readiness",       # 是否适合小红书封面
)
```

---

## 顶层输出：ImageGenerationArtifact

### Provenance（可追溯元数据）

```python
class Provenance(BaseModel):
    model_config_id: int | None = None
    model_name: str | None = None
    created_at: datetime
    knowledge_base: str | None = None
    prompt_compiler: str = "image_prompt_compiler_v1"
```

### ImageGenerationArtifact

```python
class ImageGenerationArtifact(BaseModel):
    request_id: str                              # uuid4
    status: ArtifactStatus
    source_images: list[SourceImage]
    normalized_spec: ImageEditSpec | None = None
    edit_plan: EditPlan | None = None
    compiled_prompts: CompiledPrompts | None = None
    result_assets: list[ResultAsset] = Field(default_factory=list)
    quality_report: QualityReport | None = None
    provenance: Provenance
    errors: list[str] = Field(default_factory=list)
```

**字段填充时序：**

| 状态 | 已填充字段 |
|------|-----------|
| `pending` | `request_id`, `source_images`, `provenance` |
| `planning` | + `normalized_spec`, `edit_plan` |
| `generating` | + `compiled_prompts` |
| `reviewing` | + `result_assets` |
| `completed` | + `quality_report` |
| `failed` | + `errors` |

---

## 最小可行版本范围

**本次实现（方案 A）：**
- `backend/app/schemas/image_edit.py` 中的完整 Pydantic 模型定义
- 所有枚举类型
- `HOME_DECOR_CHECK_NAMES` 常量

**暂不实现（第二阶段）：**
- prompt 编译器（`ImageEditSpec` → `CompiledPrompts`）
- home_decor 知识库
- 质量检查执行逻辑
- 新接口 `POST /ai/images/edit`
- 前端结构化表单
- 多模型自动路由
- 批量 A/B 测试

---

## 与现有代码的关系

| 现有代码 | 变化 |
|---------|------|
| `backend/app/api/ai.py` | 不改动 |
| `backend/app/services/ai_service.py` | 不改动 |
| `backend/app/schemas/image_edit.py` | **新增** |
| `POST /ai/images/generate` | 不改动，保持向后兼容 |
