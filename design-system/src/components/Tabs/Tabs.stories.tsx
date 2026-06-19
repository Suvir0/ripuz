import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { Tabs } from './Tabs';

const meta: Meta<typeof Tabs> = {
  title: 'Primitives/Tabs',
  component: Tabs,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof Tabs>;

const APP_TABS = [
  { key: 'add',      num: '01', label: 'add'      },
  { key: 'jobs',     num: '02', label: 'jobs'     },
  { key: 'library',  num: '03', label: 'library'  },
  { key: 'settings', num: '04', label: 'settings' },
];

export const Default: Story = {
  render: () => {
    const [active, setActive] = useState('add');
    return <Tabs items={APP_TABS} active={active} onChange={setActive} />;
  },
};
