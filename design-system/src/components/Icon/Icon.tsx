import React from 'react';

interface SvgProps {
  size?: number;
  className?: string;
  style?: React.CSSProperties;
}

function SvgBase({ size = 16, children, className = '', style }: SvgProps & { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      width={size}
      height={size}
      className={className}
      style={style}
    >
      {children}
    </svg>
  );
}

export const TrackIcon = (p: SvgProps) => <SvgBase {...p}><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M4.93 4.93a10 10 0 0 0 0 14.14"/></SvgBase>;
export const AlbumIcon = (p: SvgProps) => <SvgBase {...p}><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/></SvgBase>;
export const DiscographyIcon = (p: SvgProps) => <SvgBase {...p}><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></SvgBase>;
export const PlaylistIcon = (p: SvgProps) => <SvgBase {...p}><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></SvgBase>;
export const ExpandAlbumsIcon = (p: SvgProps) => <SvgBase {...p}><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></SvgBase>;
export const ExpandDiscographiesIcon = (p: SvgProps) => <SvgBase {...p}><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></SvgBase>;
export const ExplicitUpgradeIcon = (p: SvgProps) => <SvgBase {...p}><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></SvgBase>;
export const RetagLibraryIcon = (p: SvgProps) => <SvgBase {...p}><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></SvgBase>;
export const FetchLyricsIcon = (p: SvgProps) => <SvgBase {...p}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></SvgBase>;
export const FetchArtIcon = (p: SvgProps) => <SvgBase {...p}><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></SvgBase>;
export const DownloadIcon = (p: SvgProps) => <SvgBase {...p}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></SvgBase>;
export const RefreshIcon = (p: SvgProps) => <SvgBase {...p}><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></SvgBase>;
export const CloseIcon = (p: SvgProps) => <SvgBase {...p}><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></SvgBase>;
export const SearchIcon = (p: SvgProps) => <SvgBase {...p}><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></SvgBase>;

/** Returns the icon component for a given job type */
export const TYPE_ICONS: Record<string, React.FC<SvgProps>> = {
  track: TrackIcon,
  album: AlbumIcon,
  discography: DiscographyIcon,
  playlist: PlaylistIcon,
  expand_albums: ExpandAlbumsIcon,
  expand_discographies: ExpandDiscographiesIcon,
  explicit_upgrade: ExplicitUpgradeIcon,
  retag_library: RetagLibraryIcon,
  fetch_lyrics: FetchLyricsIcon,
  fetch_art: FetchArtIcon,
};

export const TYPE_LABELS: Record<string, string> = {
  track:                'single track',
  album:                'album',
  discography:          'discography',
  playlist:             'playlist',
  expand_albums:        'playlist → albums',
  expand_discographies: 'playlist → discos',
  explicit_upgrade:     'fix clean → explicit',
  retag_library:        'retag library',
  fetch_lyrics:         'fetch lyrics',
  fetch_art:            'fetch album art',
};
