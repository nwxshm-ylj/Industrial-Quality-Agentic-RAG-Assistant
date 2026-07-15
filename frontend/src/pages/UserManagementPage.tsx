import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  App as AntdApp,
  Button,
  Card,
  Col,
  Form,
  Input,
  Modal,
  Row,
  Select,
  Statistic,
  Table,
  Tag,
  Typography,
  type TableColumnsType,
} from "antd";

import { authApi } from "../api/auth";
import { getApiErrorMessage } from "../api/client";
import type { CreateUserRequest, Role, UserInfo } from "../api/types";
import { roleLabels } from "../auth/rbac";

const roleColors: Record<Role, string> = {
  admin: "error",
  engineer: "processing",
  viewer: "default",
};

export function UserManagementPage() {
  const { message } = AntdApp.useApp();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<CreateUserRequest>();
  const [createOpen, setCreateOpen] = useState(false);

  const users = useQuery({
    queryKey: ["admin", "users"],
    queryFn: authApi.listUsers,
  });
  const createUser = useMutation({
    mutationFn: authApi.createUser,
    onSuccess: async (user) => {
      message.success(`用户 ${user.username} 已创建`);
      setCreateOpen(false);
      form.resetFields();
      await queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
    onError: (error) => message.error(`创建失败：${getApiErrorMessage(error)}`),
  });

  const data = users.data || [];
  const counts = data.reduce<Record<Role, number>>(
    (result, user) => ({ ...result, [user.role]: result[user.role] + 1 }),
    { admin: 0, engineer: 0, viewer: 0 },
  );
  const columns: TableColumnsType<UserInfo> = [
    {
      title: "用户",
      dataIndex: "username",
      render: (username: string) => (
        <div className="user-identity-cell">
          <span>{username.slice(0, 1).toUpperCase()}</span>
          <strong>{username}</strong>
        </div>
      ),
    },
    {
      title: "角色",
      dataIndex: "role",
      width: 170,
      render: (role: Role) => <Tag color={roleColors[role]}>{roleLabels[role]}</Tag>,
    },
    {
      title: "账号状态",
      dataIndex: "is_active",
      width: 150,
      render: (active: boolean) => (
        <Tag color={active ? "success" : "default"} bordered={false}>
          {active ? "ACTIVE" : "DISABLED"}
        </Tag>
      ),
    },
  ];

  return (
    <div className="admin-page page-stack">
      <section className="admin-hero">
        <div>
          <Typography.Text className="page-eyebrow">IDENTITY ADMINISTRATION</Typography.Text>
          <Typography.Title level={2}>用户与角色管理</Typography.Title>
          <Typography.Paragraph>
            管理工作台访问身份。角色权限由 FastAPI RBAC 强制执行，前端仅呈现已授权能力。
          </Typography.Paragraph>
        </div>
        <Button type="primary" size="large" onClick={() => setCreateOpen(true)}>
          创建用户
        </Button>
      </section>

      <Row gutter={[14, 14]}>
        <Col xs={12} lg={6}><Card className="admin-metric"><Statistic title="用户总数" value={data.length} /></Card></Col>
        <Col xs={12} lg={6}><Card className="admin-metric"><Statistic title="管理员" value={counts.admin} /></Card></Col>
        <Col xs={12} lg={6}><Card className="admin-metric"><Statistic title="质量工程师" value={counts.engineer} /></Card></Col>
        <Col xs={12} lg={6}><Card className="admin-metric"><Statistic title="只读用户" value={counts.viewer} /></Card></Col>
      </Row>

      <Card className="admin-table-card" bordered={false}>
        <div className="section-heading">
          <div><Typography.Text className="panel-kicker">AUTHORIZED IDENTITIES</Typography.Text><Typography.Title level={4}>用户列表</Typography.Title></div>
          <Button onClick={() => users.refetch()}>刷新</Button>
        </div>
        <Table
          rowKey="username"
          columns={columns}
          dataSource={data}
          loading={users.isLoading}
          pagination={{ pageSize: 10 }}
        />
      </Card>

      <Modal
        title="创建工作台用户"
        open={createOpen}
        okText="创建用户"
        cancelText="取消"
        confirmLoading={createUser.isPending}
        onCancel={() => setCreateOpen(false)}
        onOk={() => form.submit()}
      >
        <Form<CreateUserRequest>
          form={form}
          layout="vertical"
          initialValues={{ role: "viewer" }}
          onFinish={(values) => createUser.mutate(values)}
        >
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: "请输入用户名" }, { max: 100 }]}>
            <Input autoComplete="off" placeholder="例如 quality_engineer" />
          </Form.Item>
          <Form.Item name="password" label="初始密码" rules={[{ required: true, message: "请输入密码" }, { min: 8, message: "至少 8 个字符" }]}>
            <Input.Password autoComplete="new-password" placeholder="至少 8 个字符" />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true }]}>
            <Select options={(Object.keys(roleLabels) as Role[]).map((role) => ({ value: role, label: roleLabels[role] }))} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
