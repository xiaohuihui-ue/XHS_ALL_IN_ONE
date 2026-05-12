import { MailOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Form, Input, Space, Typography } from "antd";
import { useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../../hooks/use-auth";

const { Title, Text } = Typography;

export function ForgotPasswordPage() {
  const auth = useAuth();
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await auth.forgotPassword(email);
    } catch {
      // always show the same message regardless of outcome
    } finally {
      setIsSubmitting(false);
      setSubmitted(true);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0a0a0a",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <div style={{ width: "100%", maxWidth: 400 }}>
        <Card
          style={{
            background: "#1a1a1a",
            borderColor: "#303030",
            borderRadius: 12,
          }}
          styles={{ body: { padding: "32px 28px" } }}
        >
          <Space direction="vertical" size={4} style={{ marginBottom: 24 }}>
            <Title level={4} style={{ margin: 0 }}>
              找回密码
            </Title>
            <Text type="secondary" style={{ fontSize: 13 }}>
              输入注册时使用的邮箱，我们将发送重置链接。
            </Text>
          </Space>

          {submitted ? (
            <Alert
              type="success"
              showIcon
              message="如果该邮箱已注册，你将收到一封重置密码的邮件，请查收。"
              style={{ marginBottom: 16 }}
            />
          ) : (
            <form onSubmit={handleSubmit}>
              <Form layout="vertical" component="div">
                <Form.Item label="邮箱" style={{ marginBottom: 16 }}>
                  <Input
                    prefix={<MailOutlined />}
                    placeholder="请输入邮箱地址"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    size="large"
                  />
                </Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  size="large"
                  block
                  loading={isSubmitting}
                  disabled={!email}
                >
                  发送重置邮件
                </Button>
              </Form>
            </form>
          )}

          <Text
            type="secondary"
            style={{ display: "block", textAlign: "center", marginTop: 16, fontSize: 12 }}
          >
            <Link to="/login" style={{ color: "rgba(255,255,255,0.45)" }}>
              返回登录
            </Link>
          </Text>
        </Card>
      </div>
    </div>
  );
}
