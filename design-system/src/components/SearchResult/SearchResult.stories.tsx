import type { Meta, StoryObj } from '@storybook/react';
import { SearchResult } from './SearchResult';
import { sampleSearchResults } from '../../_fixtures/search';

const meta: Meta<typeof SearchResult> = {
  title: 'Domain/SearchResult',
  component: SearchResult,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof SearchResult>;

export const Album: Story = { args: { result: sampleSearchResults[0] } };
export const Track: Story = { args: { result: sampleSearchResults[2] } };
export const Artist: Story = { args: { result: sampleSearchResults[3] } };

export const AllResults: Story = {
  render: () => (
    <div style={{ background: 'var(--paper)', padding: 12, borderRadius: 4, maxWidth: 520 }}>
      {sampleSearchResults.map(r => <SearchResult key={r.url} result={r} />)}
    </div>
  ),
};
