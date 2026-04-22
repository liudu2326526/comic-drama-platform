/* frontend/src/api/projects.ts */
import { client } from "./client";
import type {
  ProjectCreateRequest,
  ProjectCreateResponse,
  ProjectListResponse,
  ProjectParseResponse,
  ProjectRollbackRequest,
  ProjectRollbackResponse,
  ProjectUpdateRequest
} from "@/types/api";
import type { ProjectData } from "@/types";

export const projectsApi = {
  list(params?: { page?: number; page_size?: number }): Promise<ProjectListResponse> {
    return client.get("/projects", { params }).then((r) => r.data as ProjectListResponse);
  },
  create(payload: ProjectCreateRequest): Promise<ProjectCreateResponse> {
    return client.post("/projects", payload).then((r) => r.data as ProjectCreateResponse);
  },
  get(id: string): Promise<ProjectData> {
    return client.get(`/projects/${id}`).then((r) => r.data as ProjectData);
  },
  update(id: string, payload: ProjectUpdateRequest): Promise<ProjectData> {
    return client.patch(`/projects/${id}`, payload).then((r) => r.data as ProjectData);
  },
  remove(id: string): Promise<{ deleted: boolean }> {
    return client.delete(`/projects/${id}`).then((r) => r.data as { deleted: boolean });
  },
  rollback(id: string, payload: ProjectRollbackRequest): Promise<ProjectRollbackResponse> {
    return client.post(`/projects/${id}/rollback`, payload).then((r) => r.data as ProjectRollbackResponse);
  },
  parse(id: string): Promise<ProjectParseResponse> {
    // EAGER 模式后端会同步等 parse_novel + gen_storyboard 跑完,mock 足够快
    // 但接真实 LLM(M3a+)可能破 15s 默认超时。这里单独放宽到 60s。
    return client
      .post(`/projects/${id}/parse`, undefined, { timeout: 60_000 })
      .then((r) => r.data as ProjectParseResponse);
  }
};
