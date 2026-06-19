import type { Meta, StoryObj } from '@storybook/react';
import { SettingsScreen } from './SettingsScreen';

const meta: Meta<typeof SettingsScreen> = {
  title: 'Screens/SettingsScreen',
  component: SettingsScreen,
  tags: ['autodocs'],
  decorators: [(Story) => <div style={{ maxWidth: 880, padding: 24, background: 'var(--bg)' }}><Story /></div>],
};
export default meta;
type Story = StoryObj<typeof SettingsScreen>;

export const Empty: Story = {};
export const Configured: Story = {
  args: {
    settings: { downloads_dir: '/downloads', music_dir: '/music', music_quality: 27, download_lyrics: true, prefer_explicit: false },
    tokenSaved: true,
  },
};
export const Saved: Story = { args: { ...Configured.args, msgText: '✓ saved', msgVariant: 'ok', msgVisible: true } };
export const Error: Story = { args: { msgText: 'error saving', msgVariant: 'err', msgVisible: true } };
