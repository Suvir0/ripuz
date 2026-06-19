import type { Meta, StoryObj } from '@storybook/react';
import { Input } from './Input';

const meta: Meta<typeof Input> = {
  title: 'Primitives/Input',
  component: Input,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof Input>;

export const Text: Story = { args: { type: 'text', placeholder: 'Enter text…' } };
export const Password: Story = { args: { type: 'password', placeholder: 'paste your token to update' } };
export const Url: Story = { args: { type: 'url', placeholder: 'https://play.qobuz.com/track/…' } };
export const Search: Story = { args: { type: 'search', placeholder: 'Search artist or album…' } };
