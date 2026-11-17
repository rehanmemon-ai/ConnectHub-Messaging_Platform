import { useEffect, useRef } from "react";

import { initials } from "../../lib/format";
import { Icon } from "./Icon";

export function Button({ variant = "primary", busy, className = "", children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; busy?: boolean }) {
  return <button className={`button button-${variant} ${className}`} disabled={busy || props.disabled} {...props}>{busy ? <span className="spinner" aria-hidden="true"/> : null}{children}</button>;
}

export function Field({ label, error, hint, children }: { label: string; error?: string; hint?: string; children: React.ReactNode }) {
  return <label className="field"><span className="field-label">{label}</span>{children}{error ? <span className="field-error" role="alert">{error}</span> : hint ? <span className="field-hint">{hint}</span> : null}</label>;
}

export function Avatar({ name, size = "md" }: { name: string; size?: "sm" | "md" | "lg" }) {
  return <span className={`avatar avatar-${size}`} aria-hidden="true">{initials(name)}</span>;
}

export function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "accent" | "success" | "warning" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function EmptyState({ icon = "chat", title, description, action }: { icon?: "chat" | "bell" | "mail" | "search" | "users"; title: string; description: string; action?: React.ReactNode }) {
  return <div className="empty-state"><span className="empty-icon"><Icon name={icon} size={26}/></span><h3>{title}</h3><p>{description}</p>{action}</div>;
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return <div className="skeleton-stack" aria-label="Loading" role="status">{Array.from({ length: lines }, (_, index) => <span className="skeleton" key={index}/>)}</div>;
}

export function Modal({ open, title, description, onClose, children }: { open: boolean; title: string; description?: string; onClose: () => void; children: React.ReactNode }) {
  const dialog = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.focus();
    const escape = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", escape);
    return () => { window.removeEventListener("keydown", escape); previous?.focus(); };
  }, [onClose, open]);
  if (!open) return null;
  return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><div aria-describedby={description ? "modal-description" : undefined} aria-modal="true" className="modal" ref={dialog} role="dialog" tabIndex={-1}><div className="modal-heading"><div><h2>{title}</h2>{description ? <p id="modal-description">{description}</p> : null}</div><button aria-label="Close dialog" className="icon-button" onClick={onClose}><Icon name="x"/></button></div>{children}</div></div>;
}
