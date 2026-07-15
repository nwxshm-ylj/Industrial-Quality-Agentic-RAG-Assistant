import { AxiosError, type AxiosResponse } from "axios";

import { getApiErrorMessage } from "./client";

function axiosError(status: number, detail: string): AxiosError {
  const response = {
    status,
    data: { detail },
    headers: {},
    statusText: "Error",
    config: { headers: {} },
  } as unknown as AxiosResponse;
  return new AxiosError("request failed", "ERR_BAD_REQUEST", undefined, undefined, response);
}

describe("API error normalization", () => {
  it("returns FastAPI detail messages", () => {
    expect(getApiErrorMessage(axiosError(401, "用户名或密码错误"))).toBe(
      "用户名或密码错误",
    );
  });

  it("keeps local errors readable", () => {
    expect(getApiErrorMessage(new Error("local failure"))).toBe("local failure");
  });
});
