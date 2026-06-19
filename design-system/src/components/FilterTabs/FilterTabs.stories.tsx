import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { FilterTabs } from './FilterTabs';

const meta: Meta<typeof FilterTabs> = {
  title: 'Primitives/FilterTabs',
  component: FilterTabs,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof FilterTabs>;

const JOB_FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'active', label: 'Active' },
  { key: 'done', label: 'Done' },
  { key: 'error', label: 'Error' },
];

export const Default: Story = {
  render: () => {
    const [active, setActive] = useState('all');
    return <FilterTabs items={JOB_FILTERS} active={active} onChange={setActive} />;
  },
};
