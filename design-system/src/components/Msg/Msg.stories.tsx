import type { Meta, StoryObj } from '@storybook/react';
import { Msg } from './Msg';

const meta: Meta<typeof Msg> = {
  title: 'Primitives/Msg',
  component: Msg,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof Msg>;

export const Ok: Story = { args: { text: '✓ saved', variant: 'ok', visible: true } };
export const Error: Story = { args: { text: 'error saving', variant: 'err', visible: true } };
export const Hidden: Story = { args: { text: '✓ saved', variant: 'ok', visible: false } };
