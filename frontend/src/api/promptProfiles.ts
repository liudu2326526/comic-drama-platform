import { client } from "./client";
import type {
  GenerateJobAck,
  PromptProfileKind,
  PromptProfileState
} from "@/types/api";

const GENERATE_TIMEOUT_MS = 60_000;

export const promptProfilesApi = {
  generate(projectId: string, kind: PromptProfileKind): Promise<GenerateJobAck> {
    return client
      .post(`/projects/${projectId}/prompt-profiles/${kind}/generate`, undefined, {
        timeout: GENERATE_TIMEOUT_MS
      })
      .then((r) => r.data as GenerateJobAck);
  },

  updateDraft(
    projectId: string,
    kind: PromptProfileKind,
    prompt: string
  ): Promise<PromptProfileState> {
    return client
      .patch(`/projects/${projectId}/prompt-profiles/${kind}`, { prompt })
      .then((r) => r.data as PromptProfileState);
  },

  clearDraft(projectId: string, kind: PromptProfileKind): Promise<PromptProfileState> {
    return client
      .delete(`/projects/${projectId}/prompt-profiles/${kind}/draft`)
      .then((r) => r.data as PromptProfileState);
  },

  confirm(projectId: string, kind: PromptProfileKind): Promise<GenerateJobAck> {
    return client
      .post(`/projects/${projectId}/prompt-profiles/${kind}/confirm`, undefined, {
        timeout: GENERATE_TIMEOUT_MS
      })
      .then((r) => r.data as GenerateJobAck);
  }
};
