import React from 'react';

export interface TabItem {
  key: string;
  num: string;       // "01"
  label: string;     // "add"
}

export interface TabsProps {
  items: TabItem[];
  active: string;
  onChange?: (key: string) => void;
}

export function Tabs({ items, active, onChange }: TabsProps) {
  return (
    <nav className="tabs" role="tablist">
      {items.map((item) => (
        <button
          key={item.key}
          role="tab"
          className="tabs__btn"
          aria-selected={active === item.key ? 'true' : 'false'}
          onClick={() => onChange?.(item.key)}
        >
          <span className="tabs__num">{item.num}</span>
          <span>/</span>
          <span>{item.label}</span>
        </button>
      ))}
    </nav>
  );
}
