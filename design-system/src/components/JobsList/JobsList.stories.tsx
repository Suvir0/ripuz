import type { Meta, StoryObj } from '@storybook/react';
import { JobsList } from './JobsList';
import { sampleJobs } from '../../_fixtures/jobs';

const meta: Meta<typeof JobsList> = {
  title: 'Domain/JobsList',
  component: JobsList,
  tags: ['autodocs'],
  decorators: [(Story) => <div style={{ background: 'var(--bg)', padding: 24, maxWidth: 880 }}><Story /></div>],
};
export default meta;
type Story = StoryObj<typeof JobsList>;

export const Populated: Story = { args: { jobs: sampleJobs } };
export const Empty: Story = { args: { jobs: [] } };
export const ActiveOnly: Story = { args: { jobs: sampleJobs.filter(j => ['downloading', 'awaiting_confirm'].includes(j.status)) } };
