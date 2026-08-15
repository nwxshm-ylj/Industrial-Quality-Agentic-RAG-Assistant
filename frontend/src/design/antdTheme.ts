import type { ThemeConfig } from "antd";

import { designTokens } from "./tokens";

const { color, font, radius } = designTokens;

export const industrialTheme: ThemeConfig = {
  token: {
    colorPrimary: color.primary,
    colorPrimaryHover: color.primaryHover,
    colorPrimaryActive: color.primaryActive,
    colorInfo: color.info,
    colorSuccess: color.success,
    colorWarning: color.warning,
    colorError: color.danger,
    colorText: color.text,
    colorTextSecondary: color.textSecondary,
    colorBgLayout: color.canvas,
    colorBgContainer: color.surface,
    colorBgElevated: color.surface,
    colorBorder: color.border,
    colorBorderSecondary: color.borderSubtle,
    borderRadius: radius.control,
    borderRadiusLG: radius.panel,
    fontFamily: font.sans,
    fontSize: 14,
    controlHeight: 36,
    controlHeightLG: 44,
    boxShadow: "0 10px 28px rgb(20 42 56 / 8%)",
    boxShadowSecondary: "0 16px 40px rgb(20 42 56 / 12%)",
  },
  components: {
    Button: {
      controlHeightLG: 44,
      fontWeight: 600,
      primaryShadow: "none",
      borderRadius: radius.control,
    },
    Card: {
      headerBg: color.surface,
      borderRadiusLG: radius.panel,
    },
    Drawer: {
      colorBgElevated: color.surface,
    },
    Input: {
      controlHeightLG: 44,
      activeShadow: "0 0 0 2px rgb(15 118 110 / 12%)",
    },
    Menu: {
      itemBorderRadius: radius.control,
      itemHeight: 42,
    },
    Modal: {
      borderRadiusLG: radius.panel,
    },
    Segmented: {
      itemSelectedBg: color.surface,
    },
    Table: {
      headerBg: "#f3f6f7",
      headerColor: color.textSecondary,
      headerSplitColor: color.border,
      rowHoverBg: "#f2f8f7",
      cellPaddingBlock: 12,
      cellPaddingInline: 14,
      fontSize: 13,
    },
    Tabs: {
      inkBarColor: color.primary,
      itemActiveColor: color.primaryActive,
      itemHoverColor: color.primaryHover,
      itemSelectedColor: color.primary,
    },
  },
};
