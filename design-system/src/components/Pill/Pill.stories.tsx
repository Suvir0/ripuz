import type { Meta, StoryObj } from '@storybook/react';
import { Pill } from './Pill';

const meta: Meta<typeof Pill> = {
  title: 'Primitives/Pill',
  component: Pill,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof Pill>;

export const AllStatuses: Story = {
  render: () => (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', padding: 16 }}>
      <Pill status="queued" />
      <Pill status="resolving" />
      <Pill status="awaiting_confirm" />
      <Pill status="confirmed" />
      <Pill status="downloading" />
      <Pill status="tagging" />
      <Pill status="verifying" />
      <Pill status="cancelling" />
      <Pill status="done" />
      <Pill status="done_with_warnings" />
      <Pill status="error" />
      <Pill status="cancelled" />
    </div>
  ),
};

export const Done: Story = { args: { status: 'done' } };
export const Downloading: Story = { args: { status: 'downloading' } };
export const Error: Story = { args: { status: 'error' } };
export const Review: Story = { args: { status: 'awaiting_confirm' } };
