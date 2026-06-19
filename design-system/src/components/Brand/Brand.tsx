import React from 'react';

export interface BrandProps {
  version?: string;
}

export function Brand({ version = '1.0.0' }: BrandProps) {
  return (
    <div className="brand">
      <div className="brand-mark">r</div>
      <div className="brand-name">ripuz</div>
      <span className="brand-chip">{version} · flac/24-192</span>
    </div>
  );
}
