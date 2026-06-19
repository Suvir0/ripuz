import type { Meta, StoryObj } from '@storybook/react';
import { LibraryScreen } from './LibraryScreen';
import { sampleAlbums, sampleAlbumDetail, sampleStats } from '../../_fixtures/library';

const meta: Meta<typeof LibraryScreen> = {
  title: 'Screens/LibraryScreen',
  component: LibraryScreen,
  tags: ['autodocs'],
  parameters: { layout: 'fullscreen' },
  decorators: [(Story) => <div style={{ maxWidth: 880, padding: 24, background: 'var(--bg)' }}><Story /></div>],
};
export default meta;
type Story = StoryObj<typeof LibraryScreen>;

export const Default: Story = { args: { albums: sampleAlbums, stats: sampleStats } };
export const Empty: Story = { args: { albums: [], stats: { artists: 0, albums: 0, tracks: 0 } } };
export const AlbumOpen: Story = { args: { albums: sampleAlbums, stats: sampleStats, openAlbum: sampleAlbumDetail } };
