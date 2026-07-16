import React, { useState, useCallback } from 'react';
import { cls } from '../utils/format';

export function NameDialog({ open, title, label, initialValue, placeholder, confirmLabel, onSubmit, onClose }: {
  open: boolean; title: string; label?: string; initialValue?: string; placeholder?: string; confirmLabel?: string;
  onSubmit: (v: string) => void; onClose: () => void;
}) {
  const [v, setV] = useState(initialValue || '');
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="w-[400px] rounded-xl border border-tnvs-border bg-tnvs-surface p-6 shadow-tnvs-strong" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-white">{title}</h2>
        {label && <label className="tnvs-label mt-4">{label}</label>}
        <input className="tnvs-input mt-2" value={v} onChange={e => setV(e.target.value)} placeholder={placeholder} autoFocus onKeyDown={e => e.key === 'Enter' && v && (onSubmit(v), onClose())} />
        <div className="mt-4 flex justify-end gap-2">
          <button className="tnvs-btn-default" onClick={onClose}>Cancel</button>
          <button className="tnvs-btn-primary" disabled={!v.trim()} onClick={() => { onSubmit(v.trim()); onClose(); }}>{confirmLabel || 'Save'}</button>
        </div>
      </div>
    </div>
  );
}

export function ConfirmDialog({ open, title, body, confirmLabel, cancelLabel, danger, onConfirm, onClose }: {
  open: boolean; title: string; body: string; confirmLabel?: string; cancelLabel?: string; danger?: boolean;
  onConfirm: () => void; onClose: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="w-[400px] rounded-xl border border-tnvs-border bg-tnvs-surface p-6 shadow-tnvs-strong" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-white">{title}</h2>
        <p className="mt-2 text-sm text-tnvs-muted">{body}</p>
        <div className="mt-4 flex justify-end gap-2">
          <button className="tnvs-btn-default" onClick={onClose}>{cancelLabel || 'Cancel'}</button>
          <button className={danger ? 'tnvs-btn-danger' : 'tnvs-btn-primary'} onClick={() => { onConfirm(); onClose(); }}>{confirmLabel || 'Confirm'}</button>
        </div>
      </div>
    </div>
  );
}

export function Page({ title, subtitle, actions, children }: { title: string; subtitle?: string; actions?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-tnvs-border px-6 py-4">
        <div>
          <h1 className="text-lg font-semibold text-white">{title}</h1>
          {subtitle && <p className="text-xs text-tnvs-dim">{subtitle}</p>}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
      <div className="flex-1 overflow-y-auto p-6">{children}</div>
    </div>
  );
}

export function Card({ className, children, header, footer }: { className?: string; children?: React.ReactNode; header?: React.ReactNode; footer?: React.ReactNode }) {
  return (
    <div className={cls('rounded-lg border border-tnvs-border bg-tnvs-surface', className)}>
      {header && <div className="border-b border-tnvs-border px-4 py-3 text-sm font-medium text-white">{header}</div>}
      {children && <div className="p-4">{children}</div>}
      {footer && <div className="border-t border-tnvs-border px-4 py-3 text-xs text-tnvs-dim">{footer}</div>}
    </div>
  );
}

export function StatCard({ label, value, hint, accent, className }: { label: string; value: string; hint?: string; accent?: string; className?: string }) {
  return (
    <div className={cls('rounded-lg border border-tnvs-border bg-tnvs-surface p-4', className)}>
      <div className="text-[10px] font-medium uppercase tracking-wider text-tnvs-muted">{label}</div>
      <div className={cls('mt-1 font-mono text-2xl font-semibold', accent || 'text-white')}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-tnvs-dim">{hint}</div>}
    </div>
  );
}

export function Empty({ title, description, action }: { title: string; description?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="text-4xl text-tnvs-dim">∅</div>
      <h3 className="mt-4 text-base font-medium text-white">{title}</h3>
      {description && <p className="mt-1 text-sm text-tnvs-dim">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Switch({ checked, onChange, label, description, disabled }: { checked: boolean; onChange: (v: boolean) => void; label?: string; description?: string; disabled?: boolean }) {
  return (
    <label className={cls('flex items-center gap-3', disabled ? 'opacity-40' : 'cursor-pointer')}>
      <button
        role="switch" aria-checked={checked}
        onClick={() => !disabled && onChange(!checked)}
        className={cls(
          'relative inline-flex h-5 w-9 shrink-0 rounded-full transition-colors',
          checked ? 'bg-tnvs-purple' : 'bg-white/[0.12]',
        )}
      >
        <span className={cls(
          'inline-block h-4 w-4 rounded-full bg-white transition-transform mt-[2px] ml-[2px]',
          checked ? 'translate-x-4' : 'translate-x-0',
        )} />
      </button>
      <div>
        {label && <div className="text-sm text-white">{label}</div>}
        {description && <div className="text-xs text-tnvs-dim">{description}</div>}
      </div>
    </label>
  );
}

export function NumberInput({ value, onChange, min, max, step, suffix, prefix, disabled }: {
  value: number; onChange: (v: number) => void; min?: number; max?: number; step?: number; suffix?: string; prefix?: string; disabled?: boolean;
}) {
  return (
    <div className="flex items-center gap-2">
      {prefix && <span className="text-sm text-tnvs-dim">{prefix}</span>}
      <input
        type="number" value={value}
        onChange={e => onChange(parseFloat(e.target.value) || 0)}
        min={min} max={max} step={step}
        disabled={disabled}
        className="tnvs-input w-24 text-center font-mono text-sm"
      />
      {suffix && <span className="text-sm text-tnvs-dim">{suffix}</span>}
    </div>
  );
}

export function PercentInput({ value, onChange, step, min, max, disabled }: {
  value: number; onChange: (v: number) => void; step?: number; min?: number; max?: number; disabled?: boolean;
}) {
  return (
    <div className="flex items-center gap-2">
      <input
        type="number" value={(value * 100).toFixed(1)}
        onChange={e => onChange((parseFloat(e.target.value) || 0) / 100)}
        min={min != null ? min * 100 : undefined}
        max={max != null ? max * 100 : undefined}
        step={step != null ? step * 100 : 0.1}
        disabled={disabled}
        className="tnvs-input w-20 text-center font-mono text-sm"
      />
      <span className="text-sm text-tnvs-dim">%</span>
    </div>
  );
}

export function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-medium text-white">{title}</h3>
        {description && <p className="text-xs text-tnvs-dim">{description}</p>}
      </div>
      {children}
    </div>
  );
}
