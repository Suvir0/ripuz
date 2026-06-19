import type { Meta, StoryObj } from '@storybook/react';
import { Field } from './Field';

const meta: Meta<typeof Field> = {
  title: 'Primitives/Field',
  component: Field,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof Field>;

export const Default: Story = {
  args: {
    label: 'Qobuz auth token',
    labelRight: 'not set',
    required: true,
    hint: 'Never sent anywhere but your own server.',
    children: <input type="password" placeholder="paste your token to update" />,
  },
};
