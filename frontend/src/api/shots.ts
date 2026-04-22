import { client } from "./client";
import type {
  GenerateJobAck,
  RenderDraftRead,
  RenderSubmitRequest,
  RenderVersionRead,
  RenderVersionSelectResponse,
  ShotLockResponse
} from "@/types/api";

const RENDER_TIMEOUT_MS = 60_000;

export const shotsApi = {
  async renderDraft(projectId: string, shotId: string): Promise<RenderDraftRead> {
    const r = await client.post(`/projects/${projectId}/shots/${shotId}/render-draft`);
    return r.data;
  },

  async render(
    projectId: string,
    shotId: string,
    payload: RenderSubmitRequest
  ): Promise<GenerateJobAck> {
    const r = await client.post(
      `/projects/${projectId}/shots/${shotId}/render`,
      payload,
      { timeout: RENDER_TIMEOUT_MS }
    );
    return r.data;
  },

  async listRenders(projectId: string, shotId: string): Promise<RenderVersionRead[]> {
    const r = await client.get(`/projects/${projectId}/shots/${shotId}/renders`);
    return r.data;
  },

  async selectRender(
    projectId: string,
    shotId: string,
    renderId: string
  ): Promise<RenderVersionSelectResponse> {
    const r = await client.post(`/projects/${projectId}/shots/${shotId}/renders/${renderId}/select`);
    return r.data;
  },

  async lock(projectId: string, shotId: string): Promise<ShotLockResponse> {
    const r = await client.post(`/projects/${projectId}/shots/${shotId}/lock`);
    return r.data;
  }
};
