import type { Meta } from '@storybook/react';
import { AppShell } from './AppShell';
import { AddScreen } from '../AddScreen/AddScreen';
import { JobsScreen } from '../JobsScreen/JobsScreen';
import { LibraryScreen } from '../LibraryScreen/LibraryScreen';
import { SettingsScreen } from '../SettingsScreen/SettingsScreen';
import { sampleJobs } from '../../_fixtures/jobs';
import { sampleAlbums, sampleStats } from '../../_fixtures/library';

const meta: Meta = {
  title: 'Screens/FullApp',
  parameters: { layout: 'fullscreen' },
};
export default meta;

export const FullApp = {
  render: () => (
    <AppShell
      version="1.2.0"
      workerActive={sampleJobs.some(j => ['downloading', 'resolving'].includes(j.status))}
      panels={{
        add: <AddScreen />,
        jobs: <JobsScreen jobs={sampleJobs} />,
        library: <LibraryScreen albums={sampleAlbums} stats={sampleStats} />,
        settings: <SettingsScreen settings={{ downloads_dir: '/downloads', music_dir: '/music', music_quality: 27, download_lyrics: true }} tokenSaved />,
      }}
    />
  ),
};
