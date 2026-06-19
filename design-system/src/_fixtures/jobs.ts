export type JobStatus =
  | 'queued' | 'resolving' | 'awaiting_confirm' | 'confirmed'
  | 'downloading' | 'tagging' | 'verifying' | 'cancelling'
  | 'cancelled' | 'done' | 'done_with_warnings' | 'error';

export type JobType =
  | 'track' | 'album' | 'discography' | 'playlist'
  | 'expand_albums' | 'expand_discographies' | 'explicit_upgrade'
  | 'retag_library' | 'fetch_lyrics' | 'fetch_art';

export interface Job {
  id: number;
  type: JobType;
  url: string;
  status: JobStatus;
  created_at: string;
  plan?: string | null;
}

export const sampleJobs: Job[] = [
  {
    id: 7,
    type: 'album',
    url: 'https://play.qobuz.com/album/0060075347894',
    status: 'done',
    created_at: '2025-06-19 12:04',
  },
  {
    id: 6,
    type: 'playlist',
    url: 'https://play.qobuz.com/playlist/12345678',
    status: 'downloading',
    created_at: '2025-06-19 11:51',
  },
  {
    id: 5,
    type: 'discography',
    url: 'https://play.qobuz.com/artist/8024390',
    status: 'awaiting_confirm',
    created_at: '2025-06-19 11:40',
    plan: JSON.stringify({ albums: Array(14).fill(null), skipped_existing: 3, skipped_duplicate: 0, est_gb: 4.2, capped: false }),
  },
  {
    id: 4,
    type: 'album',
    url: 'https://play.qobuz.com/album/0060253781094',
    status: 'done_with_warnings',
    created_at: '2025-06-19 10:22',
  },
  {
    id: 3,
    type: 'fetch_art',
    url: 'library',
    status: 'done',
    created_at: '2025-06-18 23:10',
    plan: JSON.stringify({ missing_albums: 12, scanned_albums: 247 }),
  },
  {
    id: 2,
    type: 'retag_library',
    url: 'library',
    status: 'error',
    created_at: '2025-06-18 22:05',
  },
  {
    id: 1,
    type: 'track',
    url: 'https://play.qobuz.com/track/54321098',
    status: 'cancelled',
    created_at: '2025-06-18 18:30',
  },
];

export const sampleLog = `[pipeline] resolving playlist…
[pipeline] 14 albums discovered, 3 already present
[pipeline/download] → Portishead / Dummy
downloading track 1/11: Mysterons (7:08) …
downloading track 2/11: Sour Times (4:11) …
downloading track 3/11: Strangers (3:55) …
[tagging] running MusicBrainz Picard
[tagging] matched: Portishead / Dummy (1994) mbid=b5c24281-4c1e-4f87-8dc8-88c7b70403a7
[pipeline] done ✓`;
