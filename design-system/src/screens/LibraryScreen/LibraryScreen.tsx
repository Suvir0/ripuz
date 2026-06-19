import React, { useState } from 'react';
import type { Album, AlbumDetail as AlbumDetailData } from '../../_fixtures/library';
import { SectionHead } from '../../components/SectionHead/SectionHead';
import { StatCards } from '../../components/StatCard/StatCard';
import { LibraryGrid } from '../../components/LibraryGrid/LibraryGrid';
import { Modal } from '../../components/Modal/Modal';
import { AlbumDetail } from '../../components/AlbumDetail/AlbumDetail';

function fmtBytes(b: number): string {
  if (b >= 1e12) return (b / 1e12).toFixed(1) + ' TB';
  if (b >= 1e9)  return (b / 1e9).toFixed(1) + ' GB';
  if (b >= 1e6)  return (b / 1e6).toFixed(1) + ' MB';
  return b + ' B';
}

export interface LibraryStats {
  artists?: number;
  albums?: number;
  tracks?: number;
  total_size_bytes?: number;
  missing_art_count?: number;
  missing_lyrics_count?: number;
}

export interface LibraryScreenProps {
  albums: Album[];
  stats?: LibraryStats;
  onRefresh?: () => void;
  openAlbum?: AlbumDetailData | null;
  onAlbumClick?: (id: string) => void;
  onCloseAlbum?: () => void;
}

export function LibraryScreen({ albums, stats, onRefresh, openAlbum, onAlbumClick, onCloseAlbum }: LibraryScreenProps) {
  const [search, setSearch] = useState('');
  const [sort, setSort]     = useState('artist');

  const filtered = albums
    .filter(a => !search || (a.artist + ' ' + a.album).toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (sort === 'album')  return a.album.localeCompare(b.album);
      if (sort === 'tracks') return b.track_count - a.track_count;
      if (sort === 'size')   return b.size_bytes - a.size_bytes;
      return a.artist.localeCompare(b.artist) || a.album.localeCompare(b.album);
    });

  const statRows = stats ? [
    { key: 'artists', value: (stats.artists ?? '—').toLocaleString(), label: 'Artists' },
    { key: 'albums', value: (stats.albums ?? '—').toLocaleString(), label: 'Albums' },
    { key: 'tracks', value: (stats.tracks ?? '—').toLocaleString(), label: 'Tracks' },
    { key: 'size', value: stats.total_size_bytes != null ? fmtBytes(stats.total_size_bytes) : '—', label: 'Total size' },
    { key: 'missing-art', value: (stats.missing_art_count ?? '—').toLocaleString(), label: 'Missing art' },
    { key: 'missing-lrc', value: (stats.missing_lyrics_count ?? '—').toLocaleString(), label: 'Missing lyrics' },
  ] : [];

  return (
    <>
      <SectionHead title="Library" num="03" tag="music library" />
      {statRows.length > 0 && <StatCards stats={statRows} />}

      <LibraryGrid
        albums={filtered}
        onAlbumClick={onAlbumClick}
        onRefresh={onRefresh}
        toolbar={
          <>
            <input
              type="search"
              placeholder="Search artist or album…"
              style={{ flex: 1, maxWidth: 300 }}
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
            <select value={sort} onChange={e => setSort(e.target.value)}>
              <option value="artist">Artist A–Z</option>
              <option value="album">Album A–Z</option>
              <option value="tracks">Most tracks</option>
              <option value="size">Largest</option>
            </select>
          </>
        }
      />

      {openAlbum && (
        <Modal
          open
          title={openAlbum.album.replace(/_/g, ' ')}
          subtitle={`${openAlbum.artist.replace(/_/g, ' ')} · ${openAlbum.track_count} tracks`}
          onClose={onCloseAlbum}
        >
          <AlbumDetail detail={openAlbum} />
        </Modal>
      )}
    </>
  );
}
