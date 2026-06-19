import React from 'react';

export interface EmptyProps {
  label?: string;
  children?: React.ReactNode;
}

export function Empty({ label = 'no jobs', children }: EmptyProps) {
  return (
    <div className="empty">
      <span className="mono">{label}</span>
      {children ?? 'Paste a playlist URL on the Add tab to start a download.'}
    </div>
  );
}
