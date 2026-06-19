import type { Meta, StoryObj } from '@storybook/react';
import { AppShell } from './AppShell';

const meta: Meta<typeof AppShell> = {
  title: 'Screens/AppShell',
  component: AppShell,
  tags: ['autodocs'],
  parameters: { layout: 'fullscreen' },
};
export default meta;
type Story = StoryObj<typeof AppShell>;

export const Idle: Story = {
  args: {
    version: '1.2.0',
    workerActive: false,
    panels: {
      add:      <p style={{ padding: 24, color: 'var(--muted)' }}>Add screen content</p>,
      jobs:     <p style={{ padding: 24, color: 'var(--muted)' }}>Jobs screen content</p>,
      library:  <p style={{ padding: 24, color: 'var(--muted)' }}>Library screen content</p>,
      settings: <p style={{ padding: 24, color: 'var(--muted)' }}>Settings screen content</p>,
    },
  },
};

export const Working: Story = { args: { ...Idle.args, workerActive: true } };
