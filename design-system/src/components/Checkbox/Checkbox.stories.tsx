import type { Meta, StoryObj } from '@storybook/react';
import { Checkbox } from './Checkbox';

const meta: Meta<typeof Checkbox> = {
  title: 'Primitives/Checkbox',
  component: Checkbox,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof Checkbox>;

export const Default: Story = { args: { label: 'fetch lyrics from LRCLIB for every track', id: 'cb-lyrics' } };
export const Checked: Story = { args: { label: 'swap clean tracks for explicit twins', id: 'cb-explicit', defaultChecked: true } };
