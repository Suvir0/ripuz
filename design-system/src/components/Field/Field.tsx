import React from 'react';

export interface FieldProps {
  label: React.ReactNode;
  /** Content to the right of the label (e.g. status text) */
  labelRight?: React.ReactNode;
  required?: boolean;
  hint?: React.ReactNode;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export function Field({ label, labelRight, required, hint, children, style }: FieldProps) {
  return (
    <div className="field" style={style}>
      <div className="field-label">
        <span>
          {label}
          {required && <span className="req"> ·</span>}
        </span>
        {labelRight && <span className="mono" style={{ color: 'var(--faint)' }}>{labelRight}</span>}
      </div>
      {children}
      {hint && <div className="field-hint">{hint}</div>}
    </div>
  );
}
