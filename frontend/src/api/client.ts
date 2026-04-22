/* frontend/src/api/client.ts */
import axios, { type AxiosInstance } from "axios";
import { ApiError } from "@/utils/error";
import type { Envelope } from "@/types/api";

export const client: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 15_000,
  headers: { "Content-Type": "application/json" }
});

client.interceptors.response.use(
  (resp) => {
    const body = resp.data as Envelope<unknown> | undefined;
    if (body && typeof body.code === "number") {
      if (body.code === 0) {
        // 改写 resp.data 为裸 data,下游直接拿
        (resp as { data: unknown }).data = body.data;
        return resp;
      }
      return Promise.reject(new ApiError(body.code, body.message ?? "error", body.data));
    }
    return resp;
  },
  (err) => Promise.reject(ApiError.fromAxios(err))
);
