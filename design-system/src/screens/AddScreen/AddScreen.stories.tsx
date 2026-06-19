import type { Meta, StoryObj } from '@storybook/react';
import { AddScreen } from './AddScreen';
import { sampleSearchResults } from '../../_fixtures/search';

const meta: Meta<typeof AddScreen> = {
  title: 'Screens/AddScreen',
  component: AddScreen,
  tags: ['autodocs'],
  decorators: [(Story) => <div style={{ maxWidth: 880, padding: 24, background: 'var(--bg)' }}><Story /></div>],
};
export default meta;
type Story = StoryObj<typeof AddScreen>;

export const Default: Story = {};
export const WithSearchResults: Story = { args: { searchResults: sampleSearchResults } };
export const JobQueued: Story = { args: { msgText: '✓ job #8 queued', msgVariant: 'ok', msgVisible: true } };
export const Error: Story = { args: { msgText: 'no auth token set', msgVariant: 'err', msgVisible: true } };
