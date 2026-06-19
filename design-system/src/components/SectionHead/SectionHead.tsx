import React from 'react';

export interface SectionHeadProps {
  title: string;
  /** e.g. "01" */
  num: string;
  /** e.g. "new download" */
  tag: string;
}

export function SectionHead({ title, num, tag }: SectionHeadProps) {
  return (
    <div className="section-head">
      <h2>{title}</h2>
      <div className="section-tag">
        <b>{num}</b> / {tag}
      </div>
    </div>
  );
}
