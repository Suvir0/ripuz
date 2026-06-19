import type { Meta, StoryObj } from '@storybook/react';
import { ExplicitTag } from './ExplicitTag';

const meta: Meta<typeof ExplicitTag> = {
  title: 'Primitives/ExplicitTag',
  component: ExplicitTag,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof ExplicitTag>;

export const Default: Story = {};
