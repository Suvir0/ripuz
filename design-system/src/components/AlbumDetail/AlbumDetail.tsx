import React from 'react';
import type { AlbumDetail as AlbumDetailData } from '../../_fixtures/library';
import { QualityBadge } from '../QualityBadge/QualityBadge';

function fmtBytes(b: number): string {
  if (b >= 1e12) return (b / 1e12).toFixed(1) + ' TB';
  if (b >= 1e9)  return (b / 1e9).toFixed(1) + ' GB';
  if (b >= 1e6)  return (b / 1e6).toFixed(1) + ' MB';
  return b + ' B';
}

function fmtDuration(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h) return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  return `${m}:${String(sec).padStart(2, '0')}`;
}

export interface AlbumDetailProps {
  detail: AlbumDetailData;
}

export function AlbumDetail({ detail: d }: AlbumDetailProps) {
  const displayArtist = d.artist.replace(/_/g, ' ');
  const displayAlbum  = d.album.replace(/_/g, ' ');

  return (
    <div className="album-detail">
      <div className="album-detail-head">
        {d.cover_url ? (
          <img className="album-detail-cover" src={d.cover_url} alt="" />
        ) : (
          <div className="album-detail-cover--placeholder">♪</div>
        )}
        <div className="album-detail-info">
          <h3>{displayAlbum}</h3>
          <div className="album-detail-sub">{displayArtist}</div>
          <div className="album-detail-meta">
            {d.track_count} tracks · {fmtDuration(d.total_duration)} · {fmtBytes(d.size_bytes || 0)}
          </div>
          <div className={`album-detail-mbid album-detail-mbid--${d.mbid_present ? 'ok' : 'none'}`}>
            {d.mbid_present ? '✓ MusicBrainz matched' : 'No MusicBrainz ID'}
          </div>
        </div>
      </div>
      <table className="track-table">
        <thead>
          <tr><th>#</th><th>Title</th><th>Duration</th><th>Quality</th></tr>
        </thead>
        <tbody>
          {(d.tracks || []).map((t, i) => (
            <tr key={i}>
              <td className="track-td-num">{i + 1}</td>
              <td>
                {t.title.replace(/_/g, ' ')}
                {t.has_lyrics && <span className="track-lyrics-dot" title="has lyrics"> ♪</span>}
              </td>
              <td className="track-td-dur">{fmtDuration(t.duration)}</td>
              <td><QualityBadge bitDepth={t.bit_depth} sampleRate={t.sample_rate} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
