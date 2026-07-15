import { Button, Result } from "antd";
import { useNavigate } from "react-router-dom";

export function ForbiddenPage() {
  const navigate = useNavigate();
  return (
    <Result
      status="403"
      title="当前角色无权访问"
      subTitle="界面权限只用于改善体验，后端 FastAPI RBAC 仍会独立执行授权校验。"
      extra={<Button type="primary" onClick={() => navigate("/")}>返回工作台</Button>}
    />
  );
}
