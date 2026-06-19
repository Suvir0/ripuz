import type { Meta } from '@storybook/react';
import { TYPE_ICONS } from './Icon';

const meta: Meta = {
  title: 'Primitives/Icons',
};
export default meta;

export const AllIcons = {
  render: () => (
    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', padding: 16 }}>
      {Object.entries(TYPE_ICONS).map(([key, IconComp]) => (
        <div key={key} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, color: 'var(--muted)' }}>
          <IconComp size={20} />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{key}</span>
        </div>
      ))}
    </div>
  ),
};
