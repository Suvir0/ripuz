import type { Meta, StoryObj } from '@storybook/react';
import { ThemeToggle } from './ThemeToggle';

const meta: Meta<typeof ThemeToggle> = {
  title: 'Primitives/ThemeToggle',
  component: ThemeToggle,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof ThemeToggle>;

export const Light: Story = {};
export const Dark: Story = { parameters: { themes: { themeOverride: 'dark' } } };
