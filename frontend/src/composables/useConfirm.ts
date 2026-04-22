/* frontend/src/composables/useConfirm.ts */
import { reactive } from "vue";

export interface ConfirmOptions {
  title: string;
  body?: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
}
interface ConfirmState extends ConfirmOptions {
  open: boolean;
  resolve: ((ok: boolean) => void) | null;
}

const state = reactive<ConfirmState>({
  open: false,
  title: "",
  body: "",
  confirmText: "确认",
  cancelText: "取消",
  danger: false,
  resolve: null
});

export function useConfirmState() {
  return state;
}

export function confirm(opts: ConfirmOptions): Promise<boolean> {
  return new Promise((resolve) => {
    Object.assign(state, {
      open: true,
      confirmText: "确认",
      cancelText: "取消",
      danger: false,
      resolve,
      ...opts
    });
  });
}

export function resolveConfirm(ok: boolean) {
  state.open = false;
  state.resolve?.(ok);
  state.resolve = null;
}
