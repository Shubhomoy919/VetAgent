/* Context for opening the access-code dialog from anywhere (top bar, run bar, R shortcut). */
import { createContext, useContext } from "react";

export const AccessDialogContext = createContext<{ open: () => void }>({ open: () => undefined });

export function useAccessDialog() {
  return useContext(AccessDialogContext);
}
