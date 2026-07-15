import type { Role } from "../api/types";

export type Capability =
  | "chat:view"
  | "knowledge:view"
  | "knowledge:upload"
  | "knowledge:admin"
  | "evaluation:view"
  | "observability:view"
  | "system:health"
  | "audit:view"
  | "users:manage";

const roleCapabilities: Record<Role, ReadonlySet<Capability>> = {
  admin: new Set([
    "chat:view",
    "knowledge:view",
    "knowledge:upload",
    "knowledge:admin",
    "evaluation:view",
    "observability:view",
    "system:health",
    "audit:view",
    "users:manage",
  ]),
  engineer: new Set([
    "chat:view",
    "knowledge:view",
    "knowledge:upload",
    "evaluation:view",
    "observability:view",
    "system:health",
  ]),
  viewer: new Set(["chat:view", "knowledge:view"]),
};

export function can(role: Role | undefined, capability: Capability): boolean {
  return Boolean(role && roleCapabilities[role].has(capability));
}

export const roleLabels: Record<Role, string> = {
  admin: "系统管理员",
  engineer: "质量工程师",
  viewer: "只读用户",
};
