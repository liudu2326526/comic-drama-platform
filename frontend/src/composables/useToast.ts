/* frontend/src/composables/useToast.ts */
import { reactive } from "vue";

export type ToastVariant = "info" | "success" | "warning" | "error";
export interface ToastAction {
  label: string;
  onClick: () => void;
}
export interface ToastItem {
  id: number;
  variant: ToastVariant;
  message: string;
  detail?: string;
  action?: ToastAction;
}

const store = reactive({ items: [] as ToastItem[] });
let seq = 1;

function push(
  variant: ToastVariant,
  message: string,
  opts?: { detail?: string; action?: ToastAction; persist?: boolean }
) {
  const id = seq++;
  store.items.push({ id, variant, message, detail: opts?.detail, action: opts?.action });
  const ttl = opts?.persist ? 0 : variant === "error" ? 5000 : 3000;
  if (ttl > 0) setTimeout(() => dismiss(id), ttl);
  return id;
}

function dismiss(id: number) {
  const i = store.items.findIndex((t) => t.id === id);
  if (i >= 0) store.items.splice(i, 1);
}

export function useToast() {
  return {
    items: store.items,
    info: (m: string, o?: Parameters<typeof push>[2]) => push("info", m, o),
    success: (m: string, o?: Parameters<typeof push>[2]) => push("success", m, o),
    warning: (m: string, o?: Parameters<typeof push>[2]) => push("warning", m, o),
    error: (m: string, o?: Parameters<typeof push>[2]) => push("error", m, o),
    dismiss
  };
}
