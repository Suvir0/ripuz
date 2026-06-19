import type { Meta, StoryObj } from '@storybook/react';
import { JobsScreen } from './JobsScreen';
import { sampleJobs, sampleLog } from '../../_fixtures/jobs';

const meta: Meta<typeof JobsScreen> = {
  title: 'Screens/JobsScreen',
  component: JobsScreen,
  tags: ['autodocs'],
  parameters: { layout: 'fullscreen' },
  decorators: [(Story) => <div style={{ maxWidth: 880, padding: 24, background: 'var(--bg)' }}><Story /></div>],
};
export default meta;
type Story = StoryObj<typeof JobsScreen>;

export const Populated: Story = { args: { jobs: sampleJobs } };
export const Empty: Story = { args: { jobs: [] } };
export const LogOpen: Story = {
  args: {
    jobs: sampleJobs,
    logJob: { ...sampleJobs[1], log: sampleLog },
  },
};
