import React from 'react';

export interface StatCardProps {
  value: string | number;
  label: string;
}

export function StatCard({ value, label }: StatCardProps) {
  return (
    <div className="stat-card">
      <div className="stat-num">{value}</div>
      <div className="stat-lbl">{label}</div>
    </div>
  );
}

export interface StatCardsProps {
  stats: { key: string; value: string | number; label: string }[];
}

export function StatCards({ stats }: StatCardsProps) {
  return (
    <div className="stat-cards">
      {stats.map(s => <StatCard key={s.key} value={s.value} label={s.label} />)}
    </div>
  );
}
