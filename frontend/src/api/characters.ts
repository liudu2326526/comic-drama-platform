
/* frontend/src/api/characters.ts */
import { client } from "./client";
import type { 
  CharacterOut, 
  CharacterUpdate, 
  CharacterGenerateRequest, 
  CharacterLockRequest,
  CharacterLockResponse,
  GenerateJobAck 
} from "@/types/api";

const GENERATE_TIMEOUT_MS = 60_000; // 60s
const LOCK_TIMEOUT_MS = 30_000;    // 30s buffer for async/sync lock ops

export const charactersApi = {
  /**
   * 角色生成走异步 job(后端立即 ack), 60s timeout 仅给慢网络留 buffer。
   */
  async generate(projectId: string, payload: CharacterGenerateRequest = {}): Promise<GenerateJobAck> {
    const r = await client.post(`/projects/${projectId}/characters/generate`, payload, { 
      timeout: GENERATE_TIMEOUT_MS 
    });
    return r.data;
  },

  async list(projectId: string): Promise<CharacterOut[]> {
    const r = await client.get(`/projects/${projectId}/characters`);
    return r.data;
  },

  async update(projectId: string, characterId: string, payload: CharacterUpdate): Promise<CharacterOut> {
    const r = await client.patch(`/projects/${projectId}/characters/${characterId}`, payload);
    return r.data;
  },

  /**
   * 主角锁定走异步 job(后端立即 ack), 普通锁定本地落库; 30s timeout 仅给慢网络留 buffer。
   */
  async lock(projectId: string, characterId: string, payload: CharacterLockRequest = {}): Promise<CharacterLockResponse> {
    const r = await client.post(`/projects/${projectId}/characters/${characterId}/lock`, payload, { 
      timeout: LOCK_TIMEOUT_MS 
    });
    return r.data;
  },

  /**
   * 单项角色资产重生成
   */
  async regenerate(projectId: string, characterId: string): Promise<GenerateJobAck> {
    const r = await client.post(`/projects/${projectId}/characters/${characterId}/regenerate`, {}, { 
      timeout: GENERATE_TIMEOUT_MS 
    });
    return r.data;
  }
};
