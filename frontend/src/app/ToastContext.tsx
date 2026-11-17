/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useMemo, useState } from "react";

interface Toast { id: number; message: string; tone: "success" | "error" | "info" }
const Context = createContext<((message: string, tone?: Toast["tone"]) => void) | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((message: string, tone: Toast["tone"] = "info") => {
    const id = Date.now() + Math.random();
    setToasts((items) => [...items, { id, message, tone }]);
    window.setTimeout(() => setToasts((items) => items.filter((item) => item.id !== id)), 4200);
  }, []);
  const value = useMemo(() => push, [push]);
  return <Context.Provider value={value}>{children}<div aria-live="polite" className="toast-region">{toasts.map((toast) => <div className={`toast toast-${toast.tone}`} key={toast.id}>{toast.message}</div>)}</div></Context.Provider>;
}

export function useToast() {
  const context = useContext(Context);
  if (!context) throw new Error("useToast must be used inside ToastProvider");
  return context;
}
