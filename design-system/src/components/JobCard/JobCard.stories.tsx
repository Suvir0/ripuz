import type { Meta, StoryObj } from '@storybook/react';
import { JobCard } from './JobCard';
import { sampleJobs } from '../../_fixtures/jobs';

const meta: Meta<typeof JobCard> = {
  title: 'Domain/JobCard',
  component: JobCard,
  tags: ['autodocs'],
  decorators: [(Story) => <div style={{ background: 'var(--bg)', padding: 20 }}><Story /></div>],
};
export default meta;
type Story = StoryObj<typeof JobCard>;

export const Done: Story = { args: { job: sampleJobs[0] } };
export const Downloading: Story = { args: { job: sampleJobs[1] } };
export const AwaitingConfirm: Story = { args: { job: sampleJobs[2] } };
export const DoneWithWarnings: Story = { args: { job: sampleJobs[3] } };
export const Error: Story = { args: { job: sampleJobs[5] } };
export const Cancelled: Story = { args: { job: sampleJobs[6] } };
