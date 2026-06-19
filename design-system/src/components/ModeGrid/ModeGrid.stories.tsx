import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { ModeGrid } from './ModeGrid';
import type { JobType } from '../../_fixtures/jobs';

const meta: Meta<typeof ModeGrid> = {
  title: 'Domain/ModeGrid',
  component: ModeGrid,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof ModeGrid>;

export const Default: Story = {
  render: () => {
    const [active, setActive] = useState<JobType>('track');
    return <ModeGrid active={active} onChange={setActive} />;
  },
};
