export interface Album {
  id: string;       // "Artist/Album"
  artist: string;
  album: string;
  track_count: number;
  size_bytes: number;
  has_cover: boolean;
  cover_url?: string;
}

export interface Track {
  title: string;
  duration: number;
  bit_depth?: number;
  sample_rate?: number;
  has_lyrics: boolean;
}

export interface AlbumDetail extends Album {
  tracks: Track[];
  total_duration: number;
  mbid_present: boolean;
}

export const sampleStats = {
  artists: 142,
  albums: 521,
  tracks: 6804,
  total_size_bytes: 312_000_000_000,
  missing_art_count: 7,
  missing_lyrics_count: 94,
};

export const sampleAlbums: Album[] = [
  { id: 'Portishead/Dummy', artist: 'Portishead', album: 'Dummy', track_count: 11, size_bytes: 320_000_000, has_cover: true },
  { id: 'Radiohead/OK_Computer', artist: 'Radiohead', album: 'OK Computer', track_count: 12, size_bytes: 410_000_000, has_cover: true },
  { id: 'Nick_Cave/Murder_Ballads', artist: 'Nick Cave & The Bad Seeds', album: 'Murder Ballads', track_count: 10, size_bytes: 380_000_000, has_cover: true },
  { id: 'Massive_Attack/Mezzanine', artist: 'Massive Attack', album: 'Mezzanine', track_count: 11, size_bytes: 490_000_000, has_cover: false },
  { id: 'Aphex_Twin/Selected_Ambient_Works', artist: 'Aphex Twin', album: 'Selected Ambient Works 85-92', track_count: 13, size_bytes: 550_000_000, has_cover: true },
  { id: 'Bjork/Homogenic', artist: 'Björk', album: 'Homogenic', track_count: 10, size_bytes: 340_000_000, has_cover: true },
];

export const sampleAlbumDetail: AlbumDetail = {
  id: 'Portishead/Dummy',
  artist: 'Portishead',
  album: 'Dummy',
  track_count: 11,
  size_bytes: 320_000_000,
  has_cover: true,
  total_duration: 2867,
  mbid_present: true,
  tracks: [
    { title: 'Mysterons', duration: 428, bit_depth: 24, sample_rate: 44100, has_lyrics: true },
    { title: 'Sour Times', duration: 251, bit_depth: 24, sample_rate: 44100, has_lyrics: true },
    { title: 'Strangers', duration: 235, bit_depth: 24, sample_rate: 44100, has_lyrics: false },
    { title: 'It Could Be Sweet', duration: 284, bit_depth: 24, sample_rate: 44100, has_lyrics: true },
    { title: 'Wandering Star', duration: 282, bit_depth: 24, sample_rate: 44100, has_lyrics: true },
    { title: "It's a Fire", duration: 211, bit_depth: 24, sample_rate: 44100, has_lyrics: false },
    { title: 'Numb', duration: 224, bit_depth: 24, sample_rate: 44100, has_lyrics: true },
    { title: 'Roads', duration: 309, bit_depth: 24, sample_rate: 44100, has_lyrics: true },
    { title: 'Pedestal', duration: 234, bit_depth: 24, sample_rate: 44100, has_lyrics: false },
    { title: 'Biscuit', duration: 489, bit_depth: 24, sample_rate: 44100, has_lyrics: false },
    { title: 'Glory Box', duration: 320, bit_depth: 24, sample_rate: 44100, has_lyrics: true },
  ],
};
