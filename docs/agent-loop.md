可以，把“装修/打扮家提示词模板”升级成一个 **抽象层**，核心不是让 AI 一次性写好 Prompt，而是让 AI 按照一套固定机制：

```text
理解目标 → 生成结构化方案 → 生成 Prompt → 自评分 → 找问题 → 改写 → 再评分 → 必要时生图后再质检 → 再迭代
```

你可以把它设计成一个 **AI 自迭代提示词系统**。

---

# 一、先定义：什么叫“抽象层”

你现在有的是具体提示词：

```text
奶油风客厅、米白色沙发、原木茶几、自然光、上方留白……
```

抽象层要把它变成：

```text
内容目标
空间参数
风格参数
硬装参数
软装参数
真实感约束
平台适配约束
质量评分标准
迭代规则
```

也就是说，不要让 AI 直接写一段 Prompt，而是先让 AI 生成一个结构化对象。

---

# 二、推荐的抽象架构

可以把整个生图系统抽象成 6 层：

```text
A1 任务目标层
A2 场景变量层
A3 设计约束层
A4 生成策略层
A5 质量评估层
A6 迭代优化层
```

对应装修/打扮家主题，就是：

```text
A1：这张图要服务什么内容？
A2：空间是什么？面积多大？什么风格？
A3：哪些必须保留？哪些不能出现？
A4：怎么构图？怎么打光？怎么留白？
A5：生成前后如何评分？
A6：不达标时怎么自动修改？
```

---

# 三、抽象层核心结构

你可以设计成这个 JSON Schema：

```json
{
  "task_goal": {
    "platform": "小红书",
    "content_category": "家居装修 / 打扮家",
    "publish_goal": "提升点击率、收藏率和用户停留",
    "image_type": "封面图",
    "conversion_goal": "吸引用户收藏、评论或私信咨询"
  },
  "scene_variables": {
    "space_type": "",
    "house_type": "",
    "area": "",
    "height": "",
    "target_style": "",
    "target_mood": "",
    "budget_feeling": "",
    "user_audience": ""
  },
  "design_constraints": {
    "hard_decoration": {
      "wall": "",
      "floor": "",
      "ceiling": "",
      "window": "",
      "cabinet": ""
    },
    "soft_decoration": {
      "furniture": [],
      "decor_items": [],
      "plants": [],
      "textiles": []
    },
    "materials": [],
    "color_palette": {
      "main_colors": [],
      "secondary_colors": [],
      "accent_colors": []
    },
    "lighting": {
      "type": "",
      "temperature": "",
      "mood": ""
    }
  },
  "composition_strategy": {
    "ratio": "3:4",
    "orientation": "vertical",
    "camera_angle": "",
    "lens": "",
    "main_visual_focus": "",
    "title_space": "",
    "cover_readability": true
  },
  "realism_constraints": {
    "ordinary_home_scale": true,
    "no_luxury_mansion": true,
    "reasonable_furniture_scale": true,
    "natural_perspective": true,
    "realistic_lighting": true,
    "lived_in_but_clean": true
  },
  "negative_constraints": [
    "不要生成文字",
    "不要Logo",
    "不要水印",
    "不要二维码",
    "不要真实品牌",
    "不要豪宅化",
    "不要酒店化",
    "不要悬浮家具",
    "不要错乱透视",
    "不要畸形家具",
    "不要过度杂乱"
  ],
  "iteration_policy": {
    "max_iterations": 3,
    "target_score": 4.5,
    "must_pass_items": [
      "主题明确",
      "空间真实",
      "风格统一",
      "构图适合小红书",
      "有标题留白",
      "无文字风险"
    ]
  }
}
```

这个结构就是你的“抽象层”。

---

# 四、让 AI 自动多次迭代的核心机制

需要拆成 5 个角色节点。

```text
Planner 规划器
    ↓
Prompt Generator 提示词生成器
    ↓
Critic 质检评分器
    ↓
Rewriter 改写器
    ↓
Finalizer 最终提示词整理器
```

如果已经接入生图模型，还可以多两个节点：

```text
Image Generator 生图器
    ↓
Vision Critic 图片质检器
```

完整链路：

```text
用户需求
  ↓
Planner：生成结构化设计方案
  ↓
Prompt Generator：生成第一版生图 Prompt
  ↓
Critic：对 Prompt 评分
  ↓
如果不合格 → Rewriter 改写 Prompt
  ↓
再次 Critic 评分
  ↓
达到分数或迭代次数上限
  ↓
调用生图
  ↓
Vision Critic 检查图片
  ↓
如果图片不合格 → 生成修正 Prompt 再生图
```

---

# 五、Prompt 生成前的多轮迭代

这是“文字级迭代”，不消耗生图次数，成本低，建议一定做。

## 1. Planner 节点

让 AI 先把用户需求转成结构化方案。

### Planner Prompt

```text
你是一个小红书家居内容策划与室内设计提示词规划器。

你的任务不是直接生成图片提示词，而是先把用户需求转化为结构化的 ImagePromptSpec。

你需要判断：
1. 用户要发布什么类型的小红书内容。
2. 图片应该展示什么空间。
3. 适合什么家居风格。
4. 需要哪些硬装、软装、材质、色彩、灯光。
5. 哪些元素必须避免。
6. 图片如何适配小红书封面。

如果用户信息不足，你可以根据“小红书家居内容常用默认值”补全：
- 默认平台：小红书
- 默认图片比例：竖版 3:4
- 默认风格：奶油原木风
- 默认住宅尺度：普通中国家庭住宅
- 默认镜头：真实室内摄影，24-35mm，广角但不畸变
- 默认留白：上方 25%-30%
- 默认不生成文字、Logo、水印、二维码

请输出 JSON，不要直接输出最终 Prompt。
```

---

## 2. Prompt Generator 节点

基于结构化方案生成第一版 Prompt。

### Prompt Generator Prompt

```text
你是一个小红书家居封面生图提示词工程师。

请根据输入的 ImagePromptSpec，生成一版适合 gpt-image-2 的中文生图提示词。

要求：
1. 必须覆盖空间类型、户型面积、装修风格、硬装、软装、材质、色彩、灯光、镜头构图、生活细节、真实感约束、禁止项。
2. 语言具体、可执行，不要抽象。
3. 图片必须适合小红书家居装修封面。
4. 默认竖版 3:4。
5. 必须保留标题留白。
6. 不要让图片里直接生成文字。
7. 不要豪宅化、酒店化、别墅化。
8. 最后输出 final_image_prompt。
```

---

## 3. Critic 节点

Critic 负责给 Prompt 打分，不负责改写。

### Critic Prompt

```text
你是一个小红书家居图片提示词质检员。

请检查下面这版生图提示词是否适合生成“小红书装修/打扮家封面图”。

请按以下维度评分，每项 1-5 分：

1. topic_clarity：主题是否清晰
2. space_clarity：空间类型是否明确
3. style_consistency：装修风格是否统一
4. hard_decoration_control：硬装控制是否充分
5. soft_decoration_control：软装控制是否充分
6. material_texture_control：材质纹理是否具体
7. color_palette_control：色彩系统是否明确
8. lighting_control：灯光是否清晰
9. composition_control：构图和镜头是否可控
10. title_space_control：是否有小红书标题留白
11. realism_control：是否避免假空间、豪宅化、错乱透视
12. negative_constraints：禁止项是否完整
13. text_risk：是否存在生成乱码文字风险，分数越高风险越低
14. xiaohongshu_fit：是否适合小红书封面

请输出：
- scores
- overall_score
- failed_items
- improvement_suggestions
- whether_need_rewrite

如果 overall_score < 4.5，或者存在关键失败项，必须标记 whether_need_rewrite 为 true。
```

---

## 4. Rewriter 节点

Rewriter 根据 Critic 的问题改写 Prompt。

### Rewriter Prompt

```text
你是一个小红书家居生图提示词改写专家。

请根据原始 Prompt 和质检意见，重写一版更稳定、更适合生图的 Prompt。

改写要求：
1. 保留原始主题和核心风格。
2. 修复 Critic 指出的所有问题。
3. 增强空间尺度、硬装、软装、材质、灯光、镜头、留白、真实感控制。
4. 如果存在文字风险，强化“不要生成任何文字”。
5. 如果存在豪宅化风险，强化“普通住宅尺度，不要豪宅化”。
6. 如果构图不清晰，明确镜头位置、主体区域和留白区域。
7. 输出 rewritten_prompt。
```

---

# 六、文字级自迭代流程

你可以用伪代码实现：

```python
max_iterations = 3
target_score = 4.5

spec = planner(user_input)

prompt = prompt_generator(spec)

for i in range(max_iterations):
    review = critic(prompt)

    if review["overall_score"] >= target_score and review["whether_need_rewrite"] == False:
        break

    prompt = rewriter(
        original_prompt=prompt,
        review=review,
        spec=spec
    )

final_image_prompt = prompt
```

---

# 七、生图后的二次迭代

文字级 Prompt 合格后，再调用生图模型。

然后使用图片理解模型做质检。

```text
生成图片
  ↓
检查图片是否：
- 符合主题
- 空间比例真实
- 家具是否畸形
- 是否有错乱透视
- 是否有文字/水印/Logo
- 是否有标题留白
- 是否像小红书封面
  ↓
如果不合格，生成修正 Prompt
  ↓
重新生图
```

---

## 图片质检 JSON

```json
{
  "image_quality_check": {
    "topic_match": true,
    "space_realistic": true,
    "style_consistent": true,
    "furniture_scale_reasonable": true,
    "perspective_natural": true,
    "lighting_realistic": true,
    "has_title_space": true,
    "has_text_or_garbled_text": false,
    "has_logo_or_watermark": false,
    "too_luxury_or_hotel_like": false,
    "too_cluttered": false,
    "xiaohongshu_cover_ready": true,
    "need_retry": false,
    "retry_reason": "",
    "retry_strategy": ""
  }
}
```

---

## 图片不合格时的自动修正策略

| 问题 | 修正策略 |
|---|---|
| 出现乱码文字 | 强化“不要生成任何文字、字母、数字、标牌、海报文字” |
| 空间太豪宅 | 加入“普通住宅尺度、2.7米层高、不要挑空、不要奢华大理石” |
| 家具比例怪 | 加入“家具尺寸符合真实住宅比例，不要悬浮，不要变形” |
| 构图太满 | 加入“画面上方保留30%干净墙面留白” |
| 风格混乱 | 减少风格词，只保留一个主风格 |
| 太像样板间 | 加入“自然生活细节，有居住感但不凌乱” |
| 画面太暗 | 加入“明亮自然光，不过曝，不阴暗” |
| 背景太乱 | 加入“装饰物数量适中，保持空间呼吸感” |

---

# 八、把家居提示词变成“可迭代变量”

你不要让 AI 每次自由发挥，而是让它围绕变量做调整。

## 核心变量池

```json
{
  "space_type": ["客厅", "卧室", "餐厅", "厨房", "玄关", "阳台", "书房", "全屋"],
  "style": ["奶油风", "原木风", "中古风", "现代简约", "法式奶油", "侘寂风", "韩系温柔风", "租房改造"],
  "mood": ["温暖", "治愈", "松弛", "高级", "干净", "复古", "显大", "有生活感"],
  "camera_angle": ["入口斜拍", "平视", "窗边侧拍", "局部特写", "客厅一侧斜拍"],
  "lighting": ["白天自然光", "傍晚暖光", "自然光加辅助暖光", "柔和窗光"],
  "title_space": ["上方30%留白", "左上角25%留白", "右侧30%留白"],
  "realism_level": ["普通住宅", "小户型", "租房", "精装房改造", "老房改造"]
}
```

迭代时不是让 AI 乱改，而是让它基于评分结果调整这些变量。

例如：

```text
如果 style_consistency 分数低：
减少风格混搭，只保留一个主风格。

如果 realism_control 分数低：
增强普通住宅尺度、层高、面积、家具比例。

如果 composition_control 分数低：
明确镜头角度、主体位置和留白比例。

如果 xiaohongshu_fit 分数低：
增强封面感、留白、第一眼视觉焦点。
```

---

# 九、推荐的抽象决策规则

你可以给 AI 一套判断规则。

## 规则 1：风格最多一个主风格

```text
如果用户同时给了多个风格，例如“奶油风+中古风+法式+侘寂”，只保留一个主风格，一个辅助风格。
```

示例：

```text
主风格：奶油风
辅助风格：原木风
删除：侘寂风、法式风
```

---

## 规则 2：普通家居内容默认不要豪宅化

```text
如果主题是“小户型、租房、普通家庭、打扮家”，必须加入：
普通住宅尺度、2.6-2.8米层高、不要豪宅化、不要酒店化。
```

---

## 规则 3：小红书封面必须有留白

```text
如果图片用于封面，必须指定：
竖版3:4，上方或侧边保留25%-30%干净留白。
```

---

## 规则 4：装修设计图优先真实感

```text
如果“真实感”和“视觉冲击”冲突，优先真实感。
```

---

## 规则 5：打扮家主题必须有生活细节

```text
如果主题包含“打扮家、软装、租房改造、氛围感”，必须加入生活细节：
抱枕、薄毯、杂志、陶瓷杯、绿植、灯具。
但要求有居住感，不凌乱。
```

---

# 十、完整自迭代输出格式

你可以要求 Agent 每次输出这个结构：

```json
{
  "iteration_round": 1,
  "image_prompt_spec": {
    "task_goal": {},
    "scene_variables": {},
    "design_constraints": {},
    "composition_strategy": {},
    "realism_constraints": {},
    "negative_constraints": []
  },
  "draft_prompt": "",
  "prompt_quality_score": {
    "topic_clarity": 5,
    "space_clarity": 5,
    "style_consistency": 4,
    "hard_decoration_control": 4,
    "soft_decoration_control": 4,
    "material_texture_control": 4,
    "color_palette_control": 5,
    "lighting_control": 4,
    "composition_control": 4,
    "title_space_control": 5,
    "realism_control": 4,
    "negative_constraints": 5,
    "text_risk": 5,
    "xiaohongshu_fit": 5,
    "overall_score": 4.5
  },
  "failed_items": [],
  "improvement_suggestions": [],
  "whether_need_rewrite": false,
  "final_image_prompt": ""
}
```

---

# 十一、示例：AI 自动迭代过程

用户输入：

```text
帮我生成一张小红书封面图，主题是租房党低成本打扮家，想要温馨一点。
```

## 第 1 轮 AI 生成

```text
生成一个温馨的卧室，奶油风，适合小红书封面。
```

Critic 评分：

```json
{
  "overall_score": 2.8,
  "failed_items": [
    "空间面积不明确",
    "硬装软装不具体",
    "镜头构图不明确",
    "没有标题留白",
    "真实感控制不足"
  ],
  "whether_need_rewrite": true
}
```

---

## 第 2 轮 AI 改写

```text
生成一张适合小红书封面的竖版家居图片，比例3:4。主题是租房党低成本打扮家。空间为约12㎡普通出租屋卧室，层高约2.6米，保留普通白墙和浅木色地板，不做复杂硬装改造。风格为韩系温柔风和原木风，整体温馨、松弛、干净、可复制。

画面中有一张低矮原木床，米白色床品，小型原木床头柜，暖光床头灯，浅米色地毯，白色纱帘，角落有一盆绿植，墙面有两幅极简无文字挂画。

主色为白色、米色、浅木色，辅助色为燕麦色，点缀少量绿色植物。傍晚暖光氛围，床头灯发出柔和暖光，同时窗边有少量自然光。

镜头从卧室门口斜向拍摄，能看到床、床头柜、地毯、窗帘和绿植。画面上方保留约30%干净墙面留白，用于后期添加标题。空间尺度真实，不要过度拉伸，不要豪宅化，不要酒店化。

不要生成任何文字、Logo、水印、二维码。不要出现真实品牌。不要出现人物。不要畸形家具、悬浮家具、错乱透视。不要过度杂乱。
```

Critic 评分：

```json
{
  "overall_score": 4.7,
  "failed_items": [],
  "whether_need_rewrite": false
}
```

进入生图。

---

# 十二、关键：让 AI 不只是“重写”，而是“有策略地重写”

你需要让 Rewriter 每次说明它改了什么。

```json
{
  "rewrite_strategy": {
    "main_problem": "构图和空间尺度不够明确",
    "changes_made": [
      "增加12㎡普通出租屋卧室",
      "增加层高2.6米",
      "明确镜头从卧室门口斜向拍摄",
      "增加上方30%留白",
      "强化不要豪宅化和不要错乱透视"
    ]
  }
}
```

这样后续你能追踪为什么这版 Prompt 更好。

---

# 十三、最终建议你做成两个迭代闭环

## 闭环 1：Prompt 级迭代

```text
不调用生图，只优化提示词。
成本低，必须做。
```

适合检查：

```text
主题
空间
风格
硬装
软装
材质
灯光
构图
留白
禁止项
```

---

## 闭环 2：图片级迭代

```text
生成图片后，用视觉理解检查图片。
成本高，建议最多重试 2 次。
```

适合检查：

```text
是否真的没文字
是否真的像普通住宅
是否家具畸形
是否留白足够
是否适合小红书封面
```

---

# 十四、你可以直接使用的系统总 Prompt

```text
你是一个小红书家居装修生图 Agent，擅长将用户的装修设计、打扮家、软装搭配、租房改造、小户型改造需求，转化为高质量、可迭代的生图提示词。

你不能直接一次性输出最终 Prompt，必须按照以下流程工作：

1. 先生成 ImagePromptSpec 结构化方案。
2. 根据方案生成 draft_prompt。
3. 对 draft_prompt 进行质量评分。
4. 如果 overall_score < 4.5，必须根据评分结果自动重写。
5. 最多迭代 3 次。
6. 达到目标分数后，输出 final_image_prompt。
7. final_image_prompt 必须适合 gpt-image-2。
8. 图片默认用于小红书封面，比例为竖版 3:4。
9. 家居空间必须符合普通住宅尺度，避免豪宅化、酒店化、别墅化。
10. 必须控制空间类型、面积户型、装修风格、硬装、软装、材质、色彩、灯光、镜头构图、生活细节、真实感和禁止项。
11. 默认不要生成任何文字、Logo、水印、二维码、真实品牌。
12. 默认需要上方或侧边 25%-30% 留白，用于后期添加标题。

评分维度包括：
- 主题清晰度
- 空间清晰度
- 风格一致性
- 硬装控制
- 软装控制
- 材质纹理控制
- 色彩控制
- 灯光控制
- 构图控制
- 标题留白
- 真实感控制
- 禁止项完整度
- 文字风险
- 小红书适配度

如果评分不合格，请说明问题，并输出重写策略和新版 Prompt。
```

---

# 十五、一句话总结

你要做的不是“写一个更长的提示词”，而是搭建一个：

```text
结构化参数层
+
质量评分层
+
自动重写层
+
生图后质检层
```

让 AI 每次都按这个闭环自己优化。

最终形态应该是：

```text
用户需求
→ ImagePromptSpec
→ Draft Prompt
→ Prompt Critic
→ Prompt Rewriter
→ Final Prompt
→ 生图
→ Image Critic
→ Retry Prompt
→ 最终图片
```

这样 AI 才不是随机发挥，而是在一个可控系统里多次迭代。