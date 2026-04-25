import { client } from "./client";
import type { GenerateJobAck, StyleReferenceKind } from "@/types/api";

const GENERATE_TIMEOUT_MS = 60_000;

export const styleReferencesApi = {
  generateStyleReference(projectId: string, kind: StyleReferenceKind): Promise<GenerateJobAck> {
    const path =
      kind === "character"
        ? `/projects/${projectId}/character-style-reference/generate`
        : `/projects/${projectId}/scene-style-reference/generate`;
    return client
      .post(path, undefined, { timeout: GENERATE_TIMEOUT_MS })
      .then((r) => r.data as GenerateJobAck);
  }
};
