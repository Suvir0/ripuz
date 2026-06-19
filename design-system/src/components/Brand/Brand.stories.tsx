import type { Meta, StoryObj } from '@storybook/react';
import { Brand } from './Brand';

const meta: Meta<typeof Brand> = {
  title: 'Primitives/Brand',
  component: Brand,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof Brand>;

export const Default: Story = { args: { version: '1.2.0' } };
