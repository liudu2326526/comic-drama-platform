
/* frontend/src/api/scenes.ts */
import { client } from "./client";
import type {
  SceneOut,
  SceneUpdate,
  SceneGenerateRequest,
  SceneLockRequest,
  SceneLockResponse,
  GenerateJobAck
} from "@/types/api";

// AI 提取场景列表可能较慢。
const GENERATE_TIMEOUT_MS = 60_000; // 60s

export const scenesApi = {
  list(projectId: string): Promise<SceneOut[]> {
    return client.get(`/projects/${projectId}/scenes`).then((r) => r.data as SceneOut[]);
  },
  generate(projectId: string, payload: SceneGenerateRequest = {}): Promise<GenerateJobAck> {
    return client
      .post(`/projects/${projectId}/scenes/generate`, payload, {
        timeout: GENERATE_TIMEOUT_MS
      })
      .then((r) => r.data as GenerateJobAck);
  },
  update(projectId: string, sceneId: string, payload: SceneUpdate): Promise<SceneOut> {
    return client
      .patch(`/projects/${projectId}/scenes/${sceneId}`, payload)
      .then((r) => r.data as SceneOut);
  },
  regenerate(projectId: string, sceneId: string): Promise<GenerateJobAck> {
    return client
      .post(`/projects/${projectId}/scenes/${sceneId}/regenerate`, {}, {
        timeout: GENERATE_TIMEOUT_MS
      })
      .then((r) => r.data as GenerateJobAck);
  },
  lock(projectId: string, sceneId: string, payload: SceneLockRequest = {}): Promise<SceneLockResponse> {
    return client
      .post(`/projects/${projectId}/scenes/${sceneId}/lock`, payload, { timeout: 30_000 })
      .then((r) => r.data as SceneLockResponse);
  }
};
