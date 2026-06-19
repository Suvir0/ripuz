import type { Meta, StoryObj } from '@storybook/react';
import { AlbumDetail } from './AlbumDetail';
import { sampleAlbumDetail } from '../../_fixtures/library';

const meta: Meta<typeof AlbumDetail> = {
  title: 'Domain/AlbumDetail',
  component: AlbumDetail,
  tags: ['autodocs'],
  decorators: [(Story) => <div style={{ background: 'var(--paper)', padding: 18, maxWidth: 780 }}><Story /></div>],
};
export default meta;
type Story = StoryObj<typeof AlbumDetail>;

export const Default: Story = { args: { detail: sampleAlbumDetail } };
export const NoCover: Story = { args: { detail: { ...sampleAlbumDetail, cover_url: undefined, has_cover: false } } };
export const NoMBID: Story = { args: { detail: { ...sampleAlbumDetail, mbid_present: false } } };
