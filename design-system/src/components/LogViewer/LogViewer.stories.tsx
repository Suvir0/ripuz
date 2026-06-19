import type { Meta, StoryObj } from '@storybook/react';
import { LogViewer } from './LogViewer';
import { sampleLog } from '../../_fixtures/jobs';

const meta: Meta<typeof LogViewer> = {
  title: 'Domain/LogViewer',
  component: LogViewer,
  tags: ['autodocs'],
  decorators: [(Story) => <div style={{ background: 'var(--paper)', padding: 18, maxWidth: 780 }}><Story /></div>],
};
export default meta;
type Story = StoryObj<typeof LogViewer>;

export const Default: Story = { args: { log: sampleLog } };
export const Empty: Story = { args: { log: '' } };
