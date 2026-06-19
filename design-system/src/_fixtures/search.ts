export interface SearchResultItem {
  type: 'album' | 'track' | 'artist';
  title: string;
  artist: string;
  album?: string;
  year?: string;
  track_count?: number;
  explicit: boolean;
  cover_url?: string;
  url: string;
}

export const sampleSearchResults: SearchResultItem[] = [
  {
    type: 'album',
    title: 'Dummy',
    artist: 'Portishead',
    year: '1994',
    track_count: 11,
    explicit: false,
    cover_url: undefined,
    url: 'https://play.qobuz.com/album/0060075347894',
  },
  {
    type: 'album',
    title: 'Portishead',
    artist: 'Portishead',
    year: '1997',
    track_count: 11,
    explicit: false,
    cover_url: undefined,
    url: 'https://play.qobuz.com/album/0060253781094',
  },
  {
    type: 'track',
    title: 'Glory Box',
    artist: 'Portishead',
    album: 'Dummy',
    explicit: false,
    cover_url: undefined,
    url: 'https://play.qobuz.com/track/54321098',
  },
  {
    type: 'artist',
    title: 'Portishead',
    artist: 'Portishead',
    explicit: false,
    cover_url: undefined,
    url: 'https://play.qobuz.com/artist/8024390',
  },
];
