import React from 'react';
import type { Album } from '../../_fixtures/library';

function fmtBytes(b: number): string {
  if (b >= 1e12) return (b / 1e12).toFixed(1) + ' TB';
  if (b >= 1e9)  return (b / 1e9).toFixed(1) + ' GB';
  if (b >= 1e6)  return (b / 1e6).toFixed(1) + ' MB';
  return b + ' B';
}

export interface LibraryCardProps {
  album: Album;
  onClick?: (id: string) => void;
}

export function LibraryCard({ album, onClick }: LibraryCardProps) {
  const displayArtist = album.artist.replace(/_/g, ' ');
  const displayAlbum = album.album.replace(/_/g, ' ');

  return (
    <div className="lib-card" onClick={() => onClick?.(album.id)}>
      <div className="lib-thumb">
        {album.cover_url ? (
          <img src={album.cover_url} loading="lazy" alt="" />
        ) : (
          <div className="lib-thumb-placeholder">♪</div>
        )}
      </div>
      <div className="lib-info">
        <div className="lib-album" title={displayAlbum}>{displayAlbum}</div>
        <div className="lib-artist" title={displayArtist}>{displayArtist}</div>
        <div className="lib-meta">{album.track_count} tracks · {fmtBytes(album.size_bytes)}</div>
      </div>
    </div>
  );
}
