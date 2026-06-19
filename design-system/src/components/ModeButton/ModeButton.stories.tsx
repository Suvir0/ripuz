import type { Meta, StoryObj } from '@storybook/react';
import { ModeButton } from './ModeButton';

const meta: Meta<typeof ModeButton> = {
  title: 'Domain/ModeButton',
  component: ModeButton,
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof ModeButton>;

export const Track: Story = { args: { mode: 'track', active: false } };
export const TrackActive: Story = { args: { mode: 'track', active: true } };
export const Album: Story = { args: { mode: 'album', active: false } };
export const FetchArt: Story = { args: { mode: 'fetch_art', active: false } };
