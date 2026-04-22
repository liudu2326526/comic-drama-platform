/* frontend/tests/unit/error.spec.ts */
import { describe, it, expect } from "vitest";
import { ApiError, messageFor } from "@/utils/error";

describe("ApiError", () => {
  it("from envelope keeps code/message/data", () => {
    const err = new ApiError(40301, "forbidden", { foo: "bar" });
    expect(err.code).toBe(40301);
    expect(err.message).toBe("forbidden");
    expect(err.data).toEqual({ foo: "bar" });
  });

  it("isNetwork for falsy code", () => {
    const err = ApiError.network("network down");
    expect(err.code).toBe(0);
    expect(err.isNetwork).toBe(true);
  });
});

describe("messageFor", () => {
  it("maps known codes to chinese text", () => {
    expect(messageFor(40001)).toMatch(/参数/);
    expect(messageFor(40301)).toMatch(/阶段/);
    expect(messageFor(40401)).toMatch(/不存在/);
    expect(messageFor(42901)).toMatch(/限流/);
    expect(messageFor(50001)).toMatch(/服务异常/);
  });

  it("falls back for unknown code", () => {
    expect(messageFor(99999)).toMatch(/未知/);
  });

  it("maps 42201 to '内容违规' text", () => {
    expect(messageFor(42201)).toContain("内容违规");
  });
});
