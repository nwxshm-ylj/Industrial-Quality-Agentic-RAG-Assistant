import { useMemo, useState } from "react";
import {
  Avatar,
  Button,
  Drawer,
  Dropdown,
  Layout,
  Menu,
  Space,
  Tag,
  Tooltip,
  Typography,
  type MenuProps,
} from "antd";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { can, roleLabels } from "../auth/rbac";
import { BrandMark } from "../components/BrandMark";
import { NavGlyph } from "../components/NavGlyph";
import { useAuthStore } from "../stores/authStore";
import { useChatStore } from "../stores/chatStore";

const { Header, Sider, Content } = Layout;

const pageTitles: Record<string, { title: string; eyebrow: string }> = {
  "/": { title: "运行总览", eyebrow: "Operations overview" },
  "/chat": { title: "Agentic RAG 对话", eyebrow: "Knowledge copilot" },
  "/knowledge-base": { title: "知识库管理", eyebrow: "Knowledge lifecycle" },
  "/evaluation": { title: "RAG 评估", eyebrow: "Quality evaluation" },
  "/observability": { title: "用量与可观测性", eyebrow: "Runtime intelligence" },
  "/system-health": { title: "系统健康", eyebrow: "Service readiness" },
  "/admin/users": { title: "用户管理", eyebrow: "Identity administration" },
  "/admin/audit-logs": { title: "审计日志", eyebrow: "Security audit trail" },
  "/forbidden": { title: "访问受限", eyebrow: "Permission required" },
};

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const clearConversation = useChatStore((state) => state.clearConversation);

  const menuItems = useMemo<MenuProps["items"]>(() => {
    const role = user?.role;
    const items: MenuProps["items"] = [
      { key: "/", icon: <NavGlyph>总</NavGlyph>, label: "运行总览" },
      { key: "/chat", icon: <NavGlyph>问</NavGlyph>, label: "RAG 对话" },
      {
        key: "/knowledge-base",
        icon: <NavGlyph>知</NavGlyph>,
        label: "知识库",
      },
    ];

    if (can(role, "evaluation:view")) {
      items.push({
        key: "/evaluation",
        icon: <NavGlyph>评</NavGlyph>,
        label: "RAG 评估",
      });
    }
    if (can(role, "observability:view")) {
      items.push({
        key: "/observability",
        icon: <NavGlyph>观</NavGlyph>,
        label: "可观测性",
      });
    }
    if (can(role, "system:health")) {
      items.push({
        key: "/system-health",
        icon: <NavGlyph>健</NavGlyph>,
        label: "系统健康",
      });
    }
    if (can(role, "users:manage")) {
      items.push({
        key: "/admin/users",
        icon: <NavGlyph>管</NavGlyph>,
        label: "用户管理",
      });
    }
    if (can(role, "audit:view")) {
      items.push({
        key: "/admin/audit-logs",
        icon: <NavGlyph>审</NavGlyph>,
        label: "审计日志",
      });
    }
    return items;
  }, [user?.role]);

  const selectedKey = location.pathname;
  const pageMeta = pageTitles[selectedKey] ?? pageTitles["/"];
  const avatarText = user?.username.slice(0, 1).toUpperCase() || "U";

  const accountItems: MenuProps["items"] = [
    {
      key: "identity",
      disabled: true,
      label: (
        <div className="account-menu__identity">
          <strong>{user?.username}</strong>
          <span>{user?.role ? roleLabels[user.role] : "未知角色"}</span>
        </div>
      ),
    },
    { type: "divider" },
    {
      key: "logout",
      danger: true,
      label: "退出登录",
      onClick: () => {
        clearConversation();
        logout();
        navigate("/login", { replace: true });
      },
    },
  ];

  return (
    <Layout className="app-shell">
      <Sider
        className="app-sider"
        width={244}
        collapsedWidth={76}
        collapsed={collapsed}
        trigger={null}
      >
        <div className="app-sider__brand">
          <BrandMark compact={collapsed} />
        </div>
        <div className="app-sider__section-label">
          {collapsed ? "" : "WORKSPACE"}
        </div>
        <Menu
          className="app-menu"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
        <div className="app-sider__footer">
          {!collapsed && (
            <div>
              <span className="status-pulse" />
              <strong>Enterprise Console</strong>
              <small>Frontend Phase 6 · v0.6.0</small>
            </div>
          )}
          <Tooltip title={collapsed ? "展开导航" : "收起导航"} placement="right">
            <Button
              className="collapse-button"
              type="text"
              aria-label={collapsed ? "展开导航" : "收起导航"}
              onClick={() => setCollapsed((value) => !value)}
            >
              {collapsed ? "›" : "‹"}
            </Button>
          </Tooltip>
        </div>
      </Sider>

      <Layout className="app-main">
        <Header className="app-header">
          <Button className="mobile-nav-trigger" type="text" onClick={() => setMobileNavOpen(true)} aria-label="打开导航">☰</Button>
          <div className="app-header__title">
            <Typography.Text className="page-eyebrow">
              {pageMeta.eyebrow}
            </Typography.Text>
            <Typography.Title level={3}>{pageMeta.title}</Typography.Title>
          </div>
          <Space size={14}>
            <Tag className={`role-tag role-tag--${user?.role}`} bordered={false}>
              {user?.role ? roleLabels[user.role] : "未认证"}
            </Tag>
            <Dropdown menu={{ items: accountItems }} placement="bottomRight">
              <button className="account-trigger" type="button">
                <Avatar className="account-trigger__avatar">{avatarText}</Avatar>
                <span className="account-trigger__copy">
                  <strong>{user?.username}</strong>
                  <small>已安全登录</small>
                </span>
                <span className="account-trigger__chevron">⌄</span>
              </button>
            </Dropdown>
          </Space>
        </Header>
        <Content className="app-content">
          <Outlet />
        </Content>
        <Drawer
          className="mobile-nav-drawer"
          title={<BrandMark />}
          placement="left"
          width={286}
          open={mobileNavOpen}
          onClose={() => setMobileNavOpen(false)}
        >
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            items={menuItems}
            onClick={({ key }) => {
              navigate(key);
              setMobileNavOpen(false);
            }}
          />
        </Drawer>
      </Layout>
    </Layout>
  );
}
