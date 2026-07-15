import { Button, Result } from "antd";
import { useNavigate } from "react-router-dom";

export function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <Result
      status="404"
      title="页面不存在"
      subTitle="请从工作台导航进入有效功能。"
      extra={<Button type="primary" onClick={() => navigate("/")}>返回首页</Button>}
    />
  );
}
