import React from 'react';

export interface StatusDotProps {
  active?: boolean;
  label?: string;
}

export function StatusDot({ active = false, label }: StatusDotProps) {
  return (
    <span className={`status-dot${active ? ' status-dot--active' : ''}`}>
      {label ?? (active ? 'worker · running' : 'worker · idle')}
    </span>
  );
}
