/* frontend/src/utils/error.ts */
import type { AxiosError } from "axios";
import { ERROR_CODE, type ErrorCode } from "@/types/api";

export class ApiError extends Error {
  readonly code: number;
  readonly data: unknown;
  readonly isNetwork: boolean;

  constructor(code: number, message: string, data?: unknown, isNetwork = false) {
    super(message);
    this.code = code;
    this.data = data;
    this.isNetwork = isNetwork;
  }

  static network(msg = "网络连接失败"): ApiError {
    return new ApiError(0, msg, null, true);
  }

  static fromAxios(err: AxiosError): ApiError {
    const body = err.response?.data as { code?: number; message?: string; data?: unknown } | undefined;
    if (body && typeof body.code === "number") {
      return new ApiError(body.code, body.message ?? "服务异常", body.data);
    }
    if (err.code === "ECONNABORTED" || err.message === "Network Error") {
      return ApiError.network(err.message);
    }
    return new ApiError(ERROR_CODE.INTERNAL, err.message || "未知错误");
  }
}

const TEXT: Record<number, string> = {
  [ERROR_CODE.VALIDATION]: "参数不合法,请检查后重试",
  [ERROR_CODE.STAGE_FORBIDDEN]: "当前阶段不允许该操作",
  [ERROR_CODE.NOT_FOUND]: "资源不存在或已被删除",
  [ERROR_CODE.CONFLICT]: "业务冲突,请刷新后重试",
  [ERROR_CODE.RATE_LIMIT]: "AI 限流,请稍后重试",
  [ERROR_CODE.INTERNAL]: "服务异常,请稍后再试",
  [ERROR_CODE.UPSTREAM]: "上游服务异常,请稍后再试"
};

export function messageFor(code: number | ErrorCode, fallback?: string): string {
  return TEXT[code] ?? fallback ?? "未知错误";
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}
