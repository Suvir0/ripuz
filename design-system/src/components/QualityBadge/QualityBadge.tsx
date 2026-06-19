import React from 'react';

export interface QualityBadgeProps {
  bitDepth?: number;
  sampleRate?: number;
}

export function QualityBadge({ bitDepth, sampleRate }: QualityBadgeProps) {
  if (!bitDepth || !sampleRate) return null;
  return (
    <span className="quality-badge">
      {bitDepth}/{Math.round(sampleRate / 1000)}
    </span>
  );
}
