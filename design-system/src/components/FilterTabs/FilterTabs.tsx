import React from 'react';

export interface FilterTab {
  key: string;
  label: string;
}

export interface FilterTabsProps {
  items: FilterTab[];
  active: string;
  onChange?: (key: string) => void;
}

export function FilterTabs({ items, active, onChange }: FilterTabsProps) {
  return (
    <div className="filter-tabs" role="tablist">
      {items.map((item) => (
        <button
          key={item.key}
          className="filter-tabs__btn"
          aria-selected={active === item.key ? 'true' : 'false'}
          onClick={() => onChange?.(item.key)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
