import type { Meta, StoryObj } from '@storybook/react';
import { StatCards } from './StatCard';

const meta: Meta<typeof StatCards> = {
  title: 'Domain/StatCards',
  component: StatCards,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof StatCards>;

export const Default: Story = {
  args: {
    stats: [
      { key: 'artists', value: '142', label: 'Artists' },
      { key: 'albums', value: '521', label: 'Albums' },
      { key: 'tracks', value: '6,804', label: 'Tracks' },
      { key: 'size', value: '312 GB', label: 'Total size' },
      { key: 'missing-art', value: '7', label: 'Missing art' },
      { key: 'missing-lrc', value: '94', label: 'Missing lyrics' },
    ],
  },
};
