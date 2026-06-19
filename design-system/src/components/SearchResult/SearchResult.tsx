import React from 'react';
import type { SearchResultItem } from '../../_fixtures/search';
import { ExplicitTag } from '../ExplicitTag/ExplicitTag';
import { Button } from '../Button/Button';

function buildSub(r: SearchResultItem): string {
  if (r.type === 'artist') return 'Artist';
  if (r.type === 'track') return [r.artist, r.album].filter(Boolean).join(' · ');
  return [r.artist, r.year, r.track_count ? `${r.track_count} tracks` : ''].filter(Boolean).join(' · ');
}

export interface SearchResultProps {
  result: SearchResultItem;
  onQueue?: (url: string, type: string) => void;
}

export function SearchResult({ result, onQueue }: SearchResultProps) {
  const jobType = result.type === 'artist' ? 'discography' : result.type;
  return (
    <div className="search-result">
      {result.cover_url ? (
        <img className="search-thumb" src={result.cover_url} loading="lazy" alt="" />
      ) : (
        <div className="search-thumb--placeholder">♪</div>
      )}
      <div className="search-info">
        <div className="search-title">
          {result.title}
          {result.explicit && <ExplicitTag />}
        </div>
        <div className="search-sub">{buildSub(result)}</div>
      </div>
      <Button
        variant="ghost"
        style={{ flexShrink: 0, fontSize: 11 }}
        onClick={() => onQueue?.(result.url, jobType)}
      >
        Queue
      </Button>
    </div>
  );
}
