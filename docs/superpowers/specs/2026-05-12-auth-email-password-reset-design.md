# Auth 改进设计：注册邮箱 + 找回密码

**日期**: 2026-05-12  
**状态**: 待实现

## 背景

当前认证系统仅支持用户名 + 密码，无邮箱字段，无找回密码功能。用户反馈：
1. 注册提示"该平台账号**可能**已存在"措辞不准确（后端已明确知道账号存在）
2. 登录无找回密码入口
3. 注册无邮箱字段，无法支持密码重置

## 目标

1. 注册时必填邮箱（仅格式校验，不发验证邮件）
2. 登录页添加"忘记密码"入口
3. 实现邮件重置密码流程（JWT 令牌，30 分钟有效期）
4. 修正注册/登录错误消息
5. SMTP 配置纳入现有 YAML 体系

## 不在范围内

- 邮箱验证（注册时不发验证邮件）
- 令牌主动作废（JWT 过期即失效）
- 管理员后台
- 多用户权限管理

---

## 设计

### 1. 数据层

**`backend/app/models/user.py`** 新增字段：
```
email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
```

**Alembic 迁移**：新建一条迁移，给 `users` 表加 `email VARCHAR(254) NOT NULL UNIQUE`。  
迁移策略：直接添加（现有数据库清空重建，无需处理旧数据）。

---

### 2. 配置层

**`config/default.yaml`** 新增两处：

`server` 块加 `frontend_url`（用于构造重置邮件中的链接）：
```yaml
server:
  frontend_url: "http://localhost:5173"
```

新增 `email` 配置块：
```yaml
email:
  smtp_host: ""
  smtp_port: 587
  smtp_user: ""
  smtp_password: ""
  smtp_from: ""
  smtp_tls: true
```

**`backend/app/core/config.py`** 的 `Settings` 类新增对应字段，并加入 `yaml_key_map` 映射：
- `server.frontend_url` → `FRONTEND_URL`
- `email.*` → `EMAIL_SMTP_HOST` 等

SMTP 配置未填写时，`/forgot-password` 端点返回 503，提示管理员未配置邮件服务。

---

### 3. 后端 API

#### 3.1 Schema 拆分

`auth.py` 中的 `AuthCredentials` 拆为两个 schema：

```python
class RegisterCredentials(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)

class LoginCredentials(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6, max_length=128)
```

#### 3.2 `POST /auth/register` 修改

- 参数改为 `RegisterCredentials`
- 同时校验 username 和 email 唯一性
- username 已存在：`400 "Username already exists"`
- email 已存在：`400 "Email already exists"`

#### 3.3 新端点：`POST /auth/forgot-password`

```
Request:  { "email": "user@example.com" }
Response: 200 { "detail": "如果该邮箱已注册，重置链接已发送至邮箱。" }
```

- 无论邮箱是否存在，始终返回相同响应（防止邮箱枚举攻击）
- 邮箱存在时：生成 JWT（`token_type=password_reset`，30 分钟），发送重置邮件
- 邮件内容包含链接：`{settings.frontend_url}/reset-password?token=<jwt>`（`frontend_url` 从配置读取）

#### 3.4 新端点：`POST /auth/reset-password`

```
Request:  { "token": "<jwt>", "new_password": "..." }
Response: 200 { "detail": "密码已重置，请重新登录。" }
```

- 解码 JWT，验证 `token_type == "password_reset"` 且未过期
- 更新用户 `password_hash`
- 失败时：`400 "重置链接无效或已过期"`

#### 3.5 `security.py` 新增

```python
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 30

def create_password_reset_token(user_id: int) -> str:
    return _create_token(user_id, timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES), "password_reset")
```

验证复用现有 `decode_token()`，额外检查 `token_type == "password_reset"`。

#### 3.6 新文件：`backend/app/core/email.py`

```python
def send_password_reset_email(to_email: str, reset_url: str) -> None:
    """用 smtplib 发送重置密码邮件，从 Settings 读取 SMTP 配置。"""
```

使用标准库 `smtplib` + `email.mime`，无额外依赖。  
SMTP 未配置（smtp_host 为空）时抛出 `RuntimeError`，由端点捕获后返回 503。

---

### 4. 前端 UI

#### 4.1 注册表单（`login-page.tsx`）

- 新增邮箱输入框，位置：账号字段之下、密码字段之上
- Zod schema 新增：`email: z.string().email("请输入有效的邮箱地址")`
- `register` 模式下 schema 改为 `registerSchema`（含 email），`login` 模式保持 `loginSchema`（无 email）
- `useAuth.register` 传参加入 `email`
- `api.ts` 中 `register()` 的请求体加入 `email`

新增错误映射（`use-auth.ts` 的 `authErrorMessage`）：
```
"Email already exists" → "该邮箱已被注册，请直接登录或换一个邮箱。"
```

#### 4.2 登录表单（`login-page.tsx`）

- 密码输入框下方添加"忘记密码？"文本链接，点击跳转 `/forgot-password`
- 仅在 `mode === "login"` 时显示

#### 4.3 错误消息修正（`login-page.tsx`）

`handleSubmit` 的 catch 块中，直接使用 `error.message`（已经是 `use-auth.ts` 里精确匹配后的消息），移除重新生成 fallback 的逻辑。

#### 4.4 新页面：`/forgot-password`

文件：`frontend/src/pages/auth/forgot-password-page.tsx`

- 深色卡片样式，复用登录页设计语言
- 单个邮箱输入框
- 提交后无论成功失败，显示统一提示："如果该邮箱已注册，你将收到一封重置密码的邮件，请查收。"
- 链接注册路由（`frontend/src/router.tsx` 或对应路由文件）

#### 4.5 新页面：`/reset-password`

文件：`frontend/src/pages/auth/reset-password-page.tsx`

- 从 URL query param 读取 `token`
- 两个输入框：新密码 + 确认密码
- 提交成功后：页面切换为成功状态，显示 Alert："密码已重置，请重新登录。" + "去登录"按钮（跳转 `/login`）
- token 无效或过期：显示错误 Alert + "重新申请"链接（跳转 `/forgot-password`）

---

## 文件变更清单

| 文件 | 操作 |
|---|---|
| `backend/app/models/user.py` | 加 `email` 字段 |
| `backend/alembic/versions/<new>.py` | 新建迁移：加 email 列 |
| `backend/app/core/config.py` | 加 SMTP 配置字段 |
| `backend/app/core/email.py` | 新建：发送重置邮件 |
| `backend/app/core/security.py` | 加 `create_password_reset_token` |
| `backend/app/api/auth.py` | 拆 schema，修改 register，加两个新端点 |
| `config/default.yaml` | 加 `server.frontend_url` 和 `email` 配置块 |
| `frontend/src/lib/api.ts` | register 加 email 参数 |
| `frontend/src/hooks/use-auth.ts` | register 加 email，加错误映射，加 forgot/reset API 调用 |
| `frontend/src/pages/login/login-page.tsx` | 加邮箱字段，加忘记密码链接，修正错误消息 |
| `frontend/src/pages/auth/forgot-password-page.tsx` | 新建 |
| `frontend/src/pages/auth/reset-password-page.tsx` | 新建 |
| `frontend/src/router.tsx`（或对应文件） | 注册新路由 |
