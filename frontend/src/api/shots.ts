import { client } from "./client";
import type {
  GenerateJobAck,
  RenderDraftRead,
  RenderSubmitRequest,
  RenderVersionRead,
  RenderVersionSelectResponse,
  ShotVideoSubmitRequest,
  ShotVideoVersionRead,
  ShotVideoVersionSelectResponse,
  ShotLockResponse
} from "@/types/api";

const RENDER_TIMEOUT_MS = 60_000;

export const shotsApi = {
  async generateRenderDraft(projectId: string, shotId: string): Promise<GenerateJobAck> {
    const r = await client.post(`/projects/${projectId}/shots/${shotId}/render-draft`);
    return r.data;
  },

  async getRenderDraft(projectId: string, shotId: string): Promise<RenderDraftRead | null> {
    const r = await client.get(`/projects/${projectId}/shots/${shotId}/render-draft`);
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

  async generateVideo(
    projectId: string,
    shotId: string,
    payload: ShotVideoSubmitRequest
  ): Promise<GenerateJobAck> {
    const r = await client.post(
      `/projects/${projectId}/shots/${shotId}/video`,
      payload,
      { timeout: RENDER_TIMEOUT_MS }
    );
    return r.data;
  },

  async listRenders(projectId: string, shotId: string): Promise<RenderVersionRead[]> {
    const r = await client.get(`/projects/${projectId}/shots/${shotId}/renders`);
    return r.data;
  },

  async listVideos(projectId: string, shotId: string): Promise<ShotVideoVersionRead[]> {
    const r = await client.get(`/projects/${projectId}/shots/${shotId}/videos`);
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

  async selectVideo(
    projectId: string,
    shotId: string,
    videoId: string
  ): Promise<ShotVideoVersionSelectResponse> {
    const r = await client.post(`/projects/${projectId}/shots/${shotId}/videos/${videoId}/select`);
    return r.data;
  },

  async lock(projectId: string, shotId: string): Promise<ShotLockResponse> {
    const r = await client.post(`/projects/${projectId}/shots/${shotId}/lock`);
    return r.data;
  }
};
