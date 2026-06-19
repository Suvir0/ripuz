import type { Meta, StoryObj } from '@storybook/react';
import { LibraryCard } from './LibraryCard';
import { sampleAlbums } from '../../_fixtures/library';

const meta: Meta<typeof LibraryCard> = {
  title: 'Domain/LibraryCard',
  component: LibraryCard,
  tags: ['autodocs'],
  decorators: [(Story) => <div style={{ width: 160 }}><Story /></div>],
};
export default meta;
type Story = StoryObj<typeof LibraryCard>;

export const WithCover: Story = { args: { album: sampleAlbums[0] } };
export const NoCover: Story = { args: { album: sampleAlbums[3] } };
