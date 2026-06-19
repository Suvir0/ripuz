import type { Meta, StoryObj } from '@storybook/react';
import { StatusDot } from './StatusDot';

const meta: Meta<typeof StatusDot> = {
  title: 'Primitives/StatusDot',
  component: StatusDot,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof StatusDot>;

export const Idle: Story = { args: { active: false } };
export const Active: Story = { args: { active: true } };
