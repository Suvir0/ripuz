import React from 'react';

export interface InfoCardProps {
  title: string;
  steps: React.ReactNode[];
}

export function InfoCard({ title, steps }: InfoCardProps) {
  return (
    <div className="info-card">
      <h4>{title}</h4>
      <ol>
        {steps.map((step, i) => (
          <li key={i}>{step}</li>
        ))}
      </ol>
    </div>
  );
}
