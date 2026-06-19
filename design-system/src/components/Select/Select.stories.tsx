import type { Meta, StoryObj } from '@storybook/react';
import { Select } from './Select';

const meta: Meta<typeof Select> = {
  title: 'Primitives/Select',
  component: Select,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof Select>;

export const Quality: Story = {
  args: {
    options: [
      { value: '27', label: 'FLAC 24-bit / ≤192kHz — Max (default)' },
      { value: '7',  label: 'FLAC 24-bit / ≤96kHz — Hi-Res' },
      { value: '6',  label: 'FLAC 16-bit / 44.1kHz — CD' },
      { value: '5',  label: 'MP3 320kbps' },
    ],
    defaultValue: '27',
  },
};
