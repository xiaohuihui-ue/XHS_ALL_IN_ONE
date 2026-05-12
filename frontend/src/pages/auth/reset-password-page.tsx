import { LockOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Form, Input, Space, Typography } from "antd";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useAuth } from "../../hooks/use-auth";

const { Title, Text } = Typography;

export function ResetPasswordPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (newPassword.length < 6) {
      setError("密码至少 6 个字符。");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("两次输入的密码不一致。");
      return;
    }
    setIsSubmitting(true);
    try {
      await auth.resetPassword(token, newPassword);
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "重置链接无效或已过期");
    } finally {
      setIsSubmitting(false);
    }
  }

  const pageStyle: React.CSSProperties = {
    minHeight: "100vh",
    background: "#0a0a0a",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  };

  const cardStyle: React.CSSProperties = {
    background: "#1a1a1a",
    borderColor: "#303030",
    borderRadius: 12,
  };

  if (!token) {
    return (
      <div style={pageStyle}>
        <div style={{ width: "100%", maxWidth: 400 }}>
          <Card style={cardStyle} styles={{ body: { padding: "32px 28px" } }}>
            <Alert type="error" showIcon message="重置链接无效或已过期" style={{ marginBottom: 16 }} />
            <Link to="/forgot-password">
              <Button block>重新申请</Button>
            </Link>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div style={pageStyle}>
      <div style={{ width: "100%", maxWidth: 400 }}>
        <Card style={cardStyle} styles={{ body: { padding: "32px 28px" } }}>
          <Space direction="vertical" size={4} style={{ marginBottom: 24 }}>
            <Title level={4} style={{ margin: 0 }}>重置密码</Title>
            <Text type="secondary" style={{ fontSize: 13 }}>请输入你的新密码。</Text>
          </Space>

          {success ? (
            <>
              <Alert type="success" showIcon message="密码已重置，请重新登录。" style={{ marginBottom: 16 }} />
              <Button type="primary" block onClick={() => navigate("/login", { replace: true })}>
                去登录
              </Button>
            </>
          ) : (
            <form onSubmit={handleSubmit}>
              <Form layout="vertical" component="div">
                <Form.Item label="新密码" style={{ marginBottom: 16 }}>
                  <Input.Password
                    prefix={<LockOutlined />}
                    placeholder="至少 6 个字符"
                    autoComplete="new-password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    size="large"
                  />
                </Form.Item>
                <Form.Item label="确认新密码" style={{ marginBottom: 16 }}>
                  <Input.Password
                    prefix={<LockOutlined />}
                    placeholder="再次输入新密码"
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    size="large"
                  />
                </Form.Item>

                {error && (
                  <Alert
                    type="error"
                    showIcon
                    message={error}
                    style={{ marginBottom: 16 }}
                    action={
                      error.includes("无效或已过期") ? (
                        <Link to="/forgot-password" style={{ fontSize: 12 }}>重新申请</Link>
                      ) : undefined
                    }
                  />
                )}

                <Button type="primary" htmlType="submit" size="large" block loading={isSubmitting}>
                  确认重置
                </Button>
              </Form>
            </form>
          )}

          <Text type="secondary" style={{ display: "block", textAlign: "center", marginTop: 16, fontSize: 12 }}>
            <Link to="/login" style={{ color: "rgba(255,255,255,0.45)" }}>返回登录</Link>
          </Text>
        </Card>
      </div>
    </div>
  );
}
