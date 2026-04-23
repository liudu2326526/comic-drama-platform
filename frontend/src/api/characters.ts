
/* frontend/src/api/characters.ts */
import { client } from "./client";
import type { 
  CharacterOut, 
  CharacterUpdate, 
  CharacterGenerateRequest, 
  GenerateJobAck,
  WorkflowStageConfirmResponse
} from "@/types/api";

const GENERATE_TIMEOUT_MS = 60_000; // 60s
const ACTION_TIMEOUT_MS = 30_000;

export const charactersApi = {
  /**
   * 角色生成先返回 extract_characters 主 job,随后前端会自动接续到 gen_character_asset 主 job。
   * 60s timeout 仅给慢网络留 buffer。
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

  async registerAsset(projectId: string, characterId: string): Promise<GenerateJobAck> {
    const r = await client.post(`/projects/${projectId}/characters/${characterId}/register_asset`, {}, {
      timeout: ACTION_TIMEOUT_MS
    });
    return r.data;
  },

  async confirmStage(projectId: string): Promise<WorkflowStageConfirmResponse> {
    const r = await client.post(`/projects/${projectId}/characters/confirm`, {}, {
      timeout: ACTION_TIMEOUT_MS,
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
