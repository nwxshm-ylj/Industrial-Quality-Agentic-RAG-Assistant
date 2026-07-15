import { Button, Card, Space, Tag, Typography } from "antd";
import { useNavigate } from "react-router-dom";

interface PlaceholderPageProps {
  code: string;
  title: string;
  description: string;
  nextPhase: string;
}

export function PlaceholderPage({
  code,
  title,
  description,
  nextPhase,
}: PlaceholderPageProps) {
  const navigate = useNavigate();

  return (
    <div className="placeholder-page">
      <Card className="placeholder-card" bordered={false}>
        <span className="placeholder-card__code">{code}</span>
        <Tag color="default" bordered={false}>FOUNDATION READY</Tag>
        <Typography.Title>{title}</Typography.Title>
        <Typography.Paragraph>{description}</Typography.Paragraph>
        <div className="placeholder-card__divider" />
        <Space direction="vertical" size={2}>
          <Typography.Text strong>当前交付边界</Typography.Text>
          <Typography.Text type="secondary">
            Phase 1 仅提供受保护路由、角色菜单和页面容器；业务功能将在 {nextPhase} 验证后接入。
          </Typography.Text>
        </Space>
        <div className="placeholder-card__actions">
          <Button type="primary" onClick={() => navigate("/")}>返回运行总览</Button>
        </div>
      </Card>
    </div>
  );
}
