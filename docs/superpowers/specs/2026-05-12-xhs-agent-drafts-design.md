# XHS Agent Drafts Design

Date: 2026-05-12
Scope: Add a conversational XHS draft generation page backed by a server-side orchestration API.

## Goal

Add a new XHS page where the user can describe content requirements in a conversation-like workflow and generate multiple Xiaohongshu drafts in one run. Each generated draft must be saved into the existing draft list and can include AI-generated images attached as draft assets.

The feature uses Claude-style structured prompt engineering through the existing default text model configuration. It does not introduce a hard dependency on Claude-specific SDKs or APIs.

## Non-Goals

- Do not add a full persistent chat history system with conversation tables.
- Do not create publish jobs automatically.
- Do not replace the existing draft workbench.
- Do not require a Claude-specific provider; the current OpenAI-compatible text and image model clients remain the execution layer.
- Do not change the existing `/api/ai/generate-note` or `/api/ai/images/generate` contracts.

## User Flow

1. User opens the new XHS Agent Drafts page from the sidebar.
2. User enters a natural-language request, such as desired topics, audience, tone, quantity, content format, and image style.
3. User optionally adds reference images by upload, URL, or selecting existing image assets.
4. User sets draft count and images per draft.
5. User starts generation.
6. Backend generates structured draft content and image prompts, creates drafts, generates images, attaches images to the corresponding drafts, and returns a per-draft result.
7. Frontend displays generated draft cards with title, body summary, tags, image prompt, image previews, status, and draft IDs. to review and edit the saved drafts.

## Frontend Design

Add a new page under the XHS platform area, recommended route:

`/platforms/xhs/agent-drafts`

Add a sidebar entry near the existing draft and image workbench entries. The page follows the current Ant Design workbench style and avoids a marketing-style landing page.

Primary areas:

- Conversation/request panel: a textarea or compact message-style input for the current request.
- Generation settings panel: draft count, images per draft, optional output requirements, and reference image controls.
- Reference image picker: reuse existing upload and asset picker patterns from draft/image workflows where practical.
- Result panel: one card per generated draft with clear success/error state.

The page should use the existing API client patterns in `frontend/src/lib/api.ts` and existing type definitions in `frontend/src/types/index.ts`.

## Frontend TypeScript Types

Add the following types to `frontend/src/types/index.ts`:

```typescript
export interface AgentDraftRequestMessage {
  role: "system" | "user" | "assistant";
  content:
    | string
    | Array<
        | { type: "text"; text: string }
        | { type: "image_url"; image_url: { url: string } }
      >;
}

export interface AgentDraftPayload {
  model?: string;
  messages: AgentDraftRequestMessage[];
  n?: number;
  temperature?: number;
  top_p?: number;
  stream?: false;
  response_format?: {
    type: "json_schema";
    json_schema: {
      name: string;
      strict: boolean;
      schema: Record<string, unknown>;
    };
  };
  metadata?: {
    platform: "xhs";
    save_to_drafts?: string;
    output_requirements?: string;
  };
  image_options?: {
    model?: string;
    n?: number;
    size?: string;
    quality?: string;
    style?: string;
    response_format?: string;
  };
  user?: string;
}

export interface AgentDraftItem {
  draft: {
    id: number;
    platform: string;
    title: string;
    body: string;
    tags: Array<{ name: string }>;
    created_at: string;
  };
  image_prompt: {
    positive_prompt: string;
    negative_prompt: string;
    reference_strategy: string;
  };
  assets: Array<{
    id: number;
    draft_id: number;
    asset_type: string;
    url: string;
    local_path: string;
    sort_order: number;
  }>;
  status: "completed" | "partial" | "failed";
  errors: string[];
}

export interface AgentDraftBatchResult {
  items: AgentDraftItem[];
  created_count: number;
  failed_count: number;
}
```

Add the API client function to `frontend/src/lib/api.ts`:

```typescript
export async function generateAgentDrafts(
  payload: AgentDraftPayload
): Promise<AgentDraftBatchResult> {
  const res = await apiClient.post<{
    choices: Array<{ message: { content: string } }>;
  }>("/api/ai/agent-drafts/chat/completions", payload);
  return JSON.parse(res.data.choices[0].message.content) as AgentDraftBatchResult;
}
```

## Backend API

Add a new OpenAI-style orchestration endpoint under the existing AI router:

`POST /api/ai/agent-drafts/chat/completions`

The endpoint is domain-specific because it saves generated drafts, but its request and response should follow OpenAI Chat Completions conventions where practical.

Request shape:

```json
{
  "model": "default",
  "messages": [
    {
      "role": "system",
      "content": "You are a Xiaohongshu content strategist and visual prompt engineer."
    },
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Generate three Xiaohongshu drafts for a low-calorie breakfast audience. Tone: natural and useful."
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "https://example.test/ref.png"
          }
        }
      ]
    }
  ],
  "n": 3,
  "temperature": 0.7,
  "top_p": 1,
  "stream": false,
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "xhs_agent_draft_batch",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "drafts": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "title": { "type": "string" },
                "body": { "type": "string" },
             "tags": {
                  "type": "array",
                  "items": { "type": "string" }
                },
                "image_prompt": {
                  "type": "object",
                  "properties": {
                    "positive_prompt": { "type": "string" },
                    "negative_prompt": { "type": "string" },
                    "reference_strategy": { "type": "string" }
                  },
                  "required": ["positive_prompt", "negative_prompt", "reference_strategy"],
                  "additionalProperties": false
                }
              },
              "required": ["title", "body", "tags", "image_prompt"],
              "additionalProperties": false
            }
          }
        },
        "required": ["drafts"],
        "additionalProperties": false
      }
    }
  },
  "metadata": {
    "platform": "xhs",
    "save_to_drafts": "true",
    "output_requirements": "Each draft needs tags, a clear selling point, and one matching image prompt."
  },
  "image_options": {
    "model": "default",
    "n": 1,
    "size": "1024x1024",
    "quality": "standard",
    "style": "natural",
    "response_format": "url"
  },
  "user": "optional-end-user-id"
}
```

Validation:

- `messages` is required and follows the Chat Completions role structure.
- The latest `user` message is the current generation request.
- Text input can be either a plain string `content` or content parts with `{ "type": "text", "text": "..." }`.
- Reference images use OpenAI-style content parts: `{ "type": "image_url", "image_url": { "url": "..." } }`.
- `model` defaults to `"default"` and maps to the current user's default text model; non-default model selection can be added later through the existing model config system.
- Top-level `n` is the number of drafts to create. It defaults to 3 and is bounded to a small range, recommended 1 to 10.
- `temperature`, `top_p`, `response_format`, `metadata`, and `user` should be accepted for API familiarity even if the first implementation only uses part of them.
- `stream` must be `false` or omitted in the minimal version.
- `metadata.platform` is required and must be `xhs`.
- `metadata.output_requirements` is optional; callers can also put output requirements directly in `messages`.
- `image_options` is a local extension that mirrors OpenAI Images parameters. `image_options.n` is images per draft, defaults to 1, and is bounded to 0 to 3.

Response shape:

```json
{
  "id": "chatcmpl_xhs_agent_drafts_001",
  "object": "chat.completion",
  "created": 1778547600,
  "model": "default",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "{\"items\":[{\"draft\":{\"id\":1,\"platform\":\"xhs\",\"title\":\"Draft title\",\"body\":\"Draft body\",\"tags\":[{\"name\":\"tag\"}],\"created_at\":\"2026-05-12T09:00:00\"},\"image_prompt\":{\"positive_prompt\":\"Image generation prompt\",\"negative_prompt\":\"Things to avoid\",\"reference_strategy\":\"use_reference_images\"},\"assets\":[{\"id\":10,\"draft_id\":1,\"asset_type\":\"image\",\"url\":\"https://cdn.example.test/generated.png\",\"local_path\":\"\",\"sort_order\":1}],\"status\":\"completed\",\"errors\":[]}],\"created_count\":1,\"failed_count\":0}"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": null,
    "completion_tokens": null,
    "total_tokens": null
  }
}
```

`choices[0].message.content` is a JSON string for OpenAI compatibility. Frontend API helpers may parse this content into a typed object before passing it to page components.

Parsed assistant content shape:

```json
{
  "items": [
    {
      "draft": {
        "id": 1,
        "platform": "xhs",
        "title": "Draft title",
        "body": "Draft body",
        "tags": [{ "name": "tag" }],
        "created_at": "2026-05-12T09:00:00"
      },
      "image_prompt": {
        "positive_prompt": "Image generation prompt",
        "negative_prompt": "Things to avoid",
        "reference_strategy": "use_reference_images"
      },
      "assets": [
        {
          "id": 10,
          "draft_id": 1,
          "asset_type": "image",
          "url": "https://cdn.example.test/generated.png",
          "local_path": "",
          "sort_order": 1
        }
      ],
      "status": "completed",
      "errors": []
    }
  ],
  "created_count": 1,
  "failed_count": 0
}
```

## Prompt Engineering

Use a Claude-style structured prompt, executed by the configured default text model:

- Role: Xiaohongshu content strategist and visual prompt engineer.
- Task: produce multiple publish-ready draft candidates and matching image prompts.
- Context: user request, optional conversation context, reference image presence, output requirements.
- Constraints: preserve user requirements, return exactly the requested count, include tags, avoid unsupported claims, produce image prompts that match each draft.
- Output schema: strict JSON object with a `drafts` array.
- Quality checks: no markdown wrapper, no extra prose, each item has title, body, tags, positive prompt, negative prompt, and reference strategy.

The backend should parse and validate JSON. If the text model returns invalid JSON, return a 502-style AI generation error rather than silently creating malformed drafts.

Reference image behavior:

- If image URL content parts are present in `messages`, each image prompt must explain how to use the reference images and the image model call must receive the extracted image URL list.
- If no image URL content parts are present, the prompt is derived from the generated title, body, audience, scene, product/category, tone, and output requirements.

## Structured Output Fallback Strategy

Not all OpenAI-compatible providers support `response_format.json_schema`. The client must handle this gracefully with a two-pass approach.

**Pass 1 — native structured output:**

Send the request with `response_format: { "type": "json_schema", ... }` as specified in the request body. If the provider returns a valid JSON object that passes schema validation, use it directly.

**Pass 2 — prompt injection fallback:**

If Pass 1 fails for any of the following reasons, retry without `response_format` and instead inject the schema into the system prompt:

- The provider returns an HTTP 4xx error mentioning `response_format` or `json_schema`.
- The provider returns a response that is not valid JSON.
- The provider returns JSON that does not match the expected schema.

Fallback system prompt injection appends the following block to the system message (or creates one if absent):

```
You must respond with a single valid JSON object and nothing else.
Do not wrap the JSON in markdown code fences.
The JSON must conform to this schema:
<schema>
{"type":"object","properties":{"drafts":{"type":"array","items":{"type":"object","properties":{"title":{"type":"string"},"body":{"type":"string"},"tags":{"type":"array","items":{"type":"string"}},"image_prompt":{"type":"object","properties":{"positive_prompt":{"type":"string"},"negative_prompt":{"type":"string"},"reference_strategy":{"type":"string"}},"required":["positive_prompt","negative_prompt","reference_strategy"],"additionalProperties":false}},"required":["title","body","tags","image_prompt"],"additionalProperties":false}}},"required":["drafts"],"additionalProperties":false}
</schema>
```

After receiving the fallback response, strip any leading/trailing markdown fences (` ```json ... ``` ` or ` ``` ... ``` `) before parsing. If the result still fails JSON parsing or schema validation, return a 502 error and create no drafts.

**Implementation location:**

This two-pass logic lives in `OpenAICompatibleTextClient.generate_agent_drafts()`. The endpoint handler does not need to know which pass succeeded.

## TextAiClient Protocol Extension

Extend the `TextAiClient` Protocol in `backend/app/services/ai_service.py` with a new method:

```python
class TextAiClient(Protocol):
    # ... existing methods ...

    async def generate_agent_drafts(
        self,
        messages: list[dict],
        n: int,
        temperature: float,
        top_p: float,
        output_requirements: str | None,
        reference_image_urls: list[str],
    ) -> dict:
        """
        Returns a validated dict matching the xhs_agent_draft_batch schema:
        {"drafts": [{"title": str, "body": str, "tags": [str], "image_prompt": {...}}, ...]}
        Raises ValueError on invalid structured output after both passes.
        """
        ...
```

`OpenAICompatibleTextClient` implements this method with the two-pass fallback logic described above. The method is responsible for:

1. Building the full message list (injecting output requirements if provided).
2. Attempting Pass 1 with `response_format.json_schema`.
3. On failure, retrying with Pass 2 prompt injection.
4. Parsing, stripping markdown fences, and validating the JSON.
5. Raising `ValueError` with a descriptive message if both passes fail.

## Orchestration Behavior

The endpoint performs this sequence:

1. Load the current user's default text model and image model when needed.
2. Ask the text model for structured draft and image prompt data.
3. Validate the structured response.
4. For each generated item:
   - Create an `AiDraft` with platform `xhs`, title, body, and tags.
   - If `image_options.n` is greater than 0, call the image model for each requested image.
   - Store each generated image in `AiGeneratedAsset`.
   - Attach each generated image to the draft as a `DraftAsset`.
   - Return per-item status and errors.

Failure policy:

- Authentication failure remains 401.
- Missing default text model returns 400 before creating anything.
- Missing default image model returns 400 only when `image_options.n` is greater than 0.
- If text generation fails or returns invalid structured output, no drafts are created.
- If one draft's image generation fails after text generation succeeds, keep the text draft and return that item with partial status and an error message.
- One item's image failure should not discard other successfully generated drafts.

## Orchestration Task Recording

Use the existing `_recorded_text_task` / `_recorded_image_task` helpers from `backend/app/api/ai.py` as a reference pattern. For agent drafts, record a single top-level task of type `ai_agent_drafts_generate`.

Task payload structure:

```json
{
  "n": 3,
  "images_per_draft": 1,
  "reference_image_count": 0,
  "items": [
    {
      "index": 0,
      "draft_id": 1,
      "status": "completed",
      "asset_ids": [10],
      "errors": []
    },
    {
      "index": 1,
      "draft_id": 2,
      "status": "partial",
      "asset_ids": [],
      "errors": ["Image generation failed: upstream timeout"]
    }
  ],
  "created_count": 2,
  "failed_count": 0
}
```

The task is created before orchestration begins (status `pending`), updated to `running` when text generation starts, and finalized to `completed` or `failed` when all items are processed. Per-item results are written into `task.payload["items"]` as each item finishes, so partial progress is visible if the task is inspected mid-run.

## Data Model Impact

No migration is required for the minimal version.

Existing tables are reused:

- `ai_drafts` for generated drafts.
- `draft_assets` for images attached to drafts.
- `ai_generated_assets` for generated image records.
- `tasks` for task tracking.

### Tag Storage Format

`AiDraft.tags` is a JSON column. Store tags as a list of objects to match the format expected by the existing draft page tag renderer:

```json
[{"name": "低卡早餐"}, {"name": "健康饮食"}, {"name": "减脂"}]
```

The text model returns tags as a plain string array (`["低卡早餐", "健康饮食", "减脂"]`). The orchestration layer must convert each string to `{"name": tag}` before writing to the database.

Recommended task types:

- `ai_agent_drafts_generate` for the text planning and draft creation batch.
- Existing image task type behavior may be reused or the orchestration task payload can record per-image generation results.

## Testing

Backend tests:

- Endpoint requires authentication.
- Endpoint rejects missing default text model.
- Endpoint rejects missing image model when `image_options.n > 0`.
- Endpoint can create multiple drafts from a fake text client response.
- Tags are saved on drafts in `[{"name": "..."}]` format.
- Generated image URLs are stored as generated assets and attached to the correct drafts.
- Reference images are passed to the image client.
- Invalid JSON from the text model returns an error and creates no drafts.
- Image generation failure keeps the text draft and reports a per-item error.
- `generate_agent_drafts` uses Pass 2 fallback when the provider rejects `response_format.json_schema`.
- `generate_agent_drafts` strips markdown fences before parsing the fallback response.
- `generate_agent_drafts` raises `ValueError` when both passes return invalid JSON.

Frontend checks:

- Route is registered and sidebar entry exists.
- Page builds with TypeScript.
- Page can submit request data through the new API client function.
- Result cards show created draft IDs, statuses, and image previews.
- Existing draft page can load the created drafts.

Verification commands:

- `python -m pytest tests/backend/test_api.py`
- `python -m pytest tests/backend/test_image_edit_schema.py`
- `npm run build` in `frontend/`
- Browser check against the local app when services can be started.

## Acceptance Criteria

- A user can generate more than one Xiaohongshu draft from one request.
- Generated drafts appear in the existing draft page.
- Generated images are attached to their corresponding drafts.
- Reference images affect the image generation request when provided.
- No reference image path still produces image prompts from the generated content.
- The feature uses the existing model configuration system.
- Failures are visible per generated item and do not hide partial success.
- Structured output works against providers that do not support `response_format.json_schema` via the prompt injection fallback.
- Tags are stored and rendered correctly in the existing draft page.
