import type { Meta, StoryObj } from '@storybook/react';
import { SectionHead } from './SectionHead';

const meta: Meta<typeof SectionHead> = {
  title: 'Primitives/SectionHead',
  component: SectionHead,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof SectionHead>;

export const Default: Story = { args: { title: 'Add download', num: '01', tag: 'new download' } };
export const Jobs: Story = { args: { title: 'Jobs', num: '02', tag: 'queue & history' } };
