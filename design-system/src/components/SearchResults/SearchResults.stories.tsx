import type { Meta, StoryObj } from '@storybook/react';
import { SearchResults } from './SearchResults';
import { sampleSearchResults } from '../../_fixtures/search';

const meta: Meta<typeof SearchResults> = {
  title: 'Domain/SearchResults',
  component: SearchResults,
  tags: ['autodocs'],
  decorators: [(Story) => <div style={{ maxWidth: 520, padding: 12, background: 'var(--paper)', borderRadius: 4 }}><Story /></div>],
};
export default meta;
type Story = StoryObj<typeof SearchResults>;

export const Populated: Story = { args: { results: sampleSearchResults } };
export const Loading: Story = { args: { results: [], loading: true } };
export const NoResults: Story = { args: { results: [] } };
export const Error: Story = { args: { results: [], error: 'No Qobuz auth token set' } };
