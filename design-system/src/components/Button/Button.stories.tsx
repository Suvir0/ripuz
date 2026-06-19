import type { Meta, StoryObj } from '@storybook/react';
import { Button, ButtonRow } from './Button';

const meta: Meta<typeof Button> = {
  title: 'Primitives/Button',
  component: Button,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof Button>;

const DownloadIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
    <polyline points="7 10 12 15 17 10"/>
    <line x1="12" y1="15" x2="12" y2="3"/>
  </svg>
);

export const Default: Story = { args: { children: 'Default button' } };
export const Primary: Story = { args: { variant: 'primary', children: 'Download', icon: <DownloadIcon /> } };
export const Ghost: Story = { args: { variant: 'ghost', children: 'Refresh' } };

export const AllVariants: Story = {
  render: () => (
    <ButtonRow>
      <Button variant="primary" icon={<DownloadIcon />}>Download</Button>
      <Button>Default</Button>
      <Button variant="ghost">Ghost</Button>
    </ButtonRow>
  ),
};
