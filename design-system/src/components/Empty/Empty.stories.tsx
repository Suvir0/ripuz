import type { Meta, StoryObj } from '@storybook/react';
import { Empty } from './Empty';

const meta: Meta<typeof Empty> = {
  title: 'Primitives/Empty',
  component: Empty,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof Empty>;

export const NoJobs: Story = {};
export const NoResults: Story = { args: { label: 'no results', children: 'Try a different search query.' } };
