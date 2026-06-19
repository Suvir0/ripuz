import type { Meta, StoryObj } from '@storybook/react';
import { QualityBadge } from './QualityBadge';

const meta: Meta<typeof QualityBadge> = {
  title: 'Primitives/QualityBadge',
  component: QualityBadge,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof QualityBadge>;

export const HiRes: Story = { args: { bitDepth: 24, sampleRate: 44100 } };
export const MaxRes: Story = { args: { bitDepth: 24, sampleRate: 192000 } };
