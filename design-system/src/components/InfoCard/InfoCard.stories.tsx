import type { Meta, StoryObj } from '@storybook/react';
import { InfoCard } from './InfoCard';

const meta: Meta<typeof InfoCard> = {
  title: 'Primitives/InfoCard',
  component: InfoCard,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof InfoCard>;

export const Default: Story = {
  args: {
    title: 'How to get your Qobuz auth token',
    steps: [
      <>Log in at <code>play.qobuz.com</code></>,
      <>Press <kbd>F12</kbd> → <b>Application</b> → <b>Local Storage</b> → <code>https://play.qobuz.com</code></>,
      <>Find the <code>localuser</code> key, copy the <code>token</code> string from its JSON value</>,
    ],
  },
};
