import type { Meta, StoryObj } from '@storybook/react';
import { LibraryGrid } from './LibraryGrid';
import { sampleAlbums } from '../../_fixtures/library';

const meta: Meta<typeof LibraryGrid> = {
  title: 'Domain/LibraryGrid',
  component: LibraryGrid,
  tags: ['autodocs'],
  decorators: [(Story) => <div style={{ maxWidth: 880, padding: 24 }}><Story /></div>],
};
export default meta;
type Story = StoryObj<typeof LibraryGrid>;

export const Default: Story = { args: { albums: sampleAlbums } };
export const WithMore: Story = { args: { albums: sampleAlbums.slice(0, 4), hasMore: true, remaining: 517 } };
