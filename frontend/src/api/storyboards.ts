/* frontend/src/api/storyboards.ts */
import { client } from "./client";
import type {
  BindSceneRequest,
  BindSceneResponse,
  StoryboardConfirmResponse,
  StoryboardCreateRequest,
  StoryboardDeleteResponse,
  StoryboardDetail,
  StoryboardReorderRequest,
  StoryboardReorderResponse,
  StoryboardUpdateRequest
} from "@/types/api";

export const storyboardsApi = {
  list(projectId: string): Promise<StoryboardDetail[]> {
    return client
      .get(`/projects/${projectId}/storyboards`)
      .then((r) => r.data as StoryboardDetail[]);
  },
  create(projectId: string, payload: StoryboardCreateRequest): Promise<StoryboardDetail> {
    return client
      .post(`/projects/${projectId}/storyboards`, payload)
      .then((r) => r.data as StoryboardDetail);
  },
  update(
    projectId: string,
    shotId: string,
    payload: StoryboardUpdateRequest
  ): Promise<StoryboardDetail> {
    return client
      .patch(`/projects/${projectId}/storyboards/${shotId}`, payload)
      .then((r) => r.data as StoryboardDetail);
  },
  remove(projectId: string, shotId: string): Promise<StoryboardDeleteResponse> {
    return client
      .delete(`/projects/${projectId}/storyboards/${shotId}`)
      .then((r) => r.data as StoryboardDeleteResponse);
  },
  reorder(
    projectId: string,
    payload: StoryboardReorderRequest
  ): Promise<StoryboardReorderResponse> {
    return client
      .post(`/projects/${projectId}/storyboards/reorder`, payload)
      .then((r) => r.data as StoryboardReorderResponse);
  },
  confirm(projectId: string): Promise<StoryboardConfirmResponse> {
    return client
      .post(`/projects/${projectId}/storyboards/confirm`)
      .then((r) => r.data as StoryboardConfirmResponse);
  },
  bindScene(
    projectId: string,
    shotId: string,
    payload: BindSceneRequest
  ): Promise<BindSceneResponse> {
    return client
      .post(`/projects/${projectId}/storyboards/${shotId}/bind_scene`, payload)
      .then((r) => r.data as BindSceneResponse);
  }
};
