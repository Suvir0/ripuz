import type { Meta, StoryObj } from '@storybook/react';
import { Modal } from './Modal';

const meta: Meta<typeof Modal> = {
  title: 'Domain/Modal',
  component: Modal,
  tags: ['autodocs'],
  parameters: { layout: 'fullscreen' },
};
export default meta;
type Story = StoryObj<typeof Modal>;

export const LogModal: Story = {
  args: {
    open: true,
    title: 'Job #006 log',
    subtitle: 'playlist · downloading',
    children: <pre style={{ fontFamily: 'var(--font-mono)', fontSize: 12, lineHeight: 1.6, color: 'var(--ink-soft)' }}>
      01 [pipeline] resolving playlist…{'\n'}
      02 [pipeline] 14 albums discovered{'\n'}
      03 downloading track 1/11: Mysterons (7:08) …{'\n'}
    </pre>,
  },
};

export const ReviewModal: Story = {
  args: {
    open: true,
    title: 'Job #005 log',
    subtitle: 'discography · review',
    planText: '14 album(s) to download · 3 already present · ~4.2 GB',
    actions: (
      <>
        <button className="btn-confirm">Confirm download</button>
        <button className="btn-cancel-job">Cancel job</button>
      </>
    ),
    children: <pre style={{ fontFamily: 'var(--font-mono)', fontSize: 12, lineHeight: 1.6, color: 'var(--ink-soft)' }}>
      01 [pipeline] resolving discography…{'\n'}
      02 found 14 new albums{'\n'}
    </pre>,
  },
};
