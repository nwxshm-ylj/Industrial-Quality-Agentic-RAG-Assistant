import { can } from "./rbac";

describe("role capabilities", () => {
  it("allows every role to open chat and knowledge pages", () => {
    expect(can("admin", "chat:view")).toBe(true);
    expect(can("engineer", "knowledge:view")).toBe(true);
    expect(can("viewer", "chat:view")).toBe(true);
  });

  it("keeps evaluation and observability hidden from viewer", () => {
    expect(can("viewer", "evaluation:view")).toBe(false);
    expect(can("viewer", "observability:view")).toBe(false);
    expect(can("engineer", "evaluation:view")).toBe(true);
  });

  it("allows only admin to manage users", () => {
    expect(can("admin", "users:manage")).toBe(true);
    expect(can("engineer", "users:manage")).toBe(false);
    expect(can("viewer", "users:manage")).toBe(false);
  });

  it("separates health visibility from sensitive audit access", () => {
    expect(can("admin", "system:health")).toBe(true);
    expect(can("engineer", "system:health")).toBe(true);
    expect(can("viewer", "system:health")).toBe(false);
    expect(can("admin", "audit:view")).toBe(true);
    expect(can("engineer", "audit:view")).toBe(false);
    expect(can("viewer", "audit:view")).toBe(false);
  });

  it("matches document lifecycle permissions enforced by FastAPI", () => {
    expect(can("admin", "knowledge:upload")).toBe(true);
    expect(can("admin", "knowledge:admin")).toBe(true);
    expect(can("engineer", "knowledge:upload")).toBe(true);
    expect(can("engineer", "knowledge:admin")).toBe(false);
    expect(can("viewer", "knowledge:upload")).toBe(false);
    expect(can("viewer", "knowledge:admin")).toBe(false);
  });
});
