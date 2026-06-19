import React, { useState } from 'react';
import type { JobType } from '../../_fixtures/jobs';
import { SectionHead } from '../../components/SectionHead/SectionHead';
import { Card } from '../../components/Card/Card';
import { ModeGrid } from '../../components/ModeGrid/ModeGrid';
import { Field } from '../../components/Field/Field';
import { Button, ButtonRow } from '../../components/Button/Button';
import { Msg } from '../../components/Msg/Msg';
import { SearchResults } from '../../components/SearchResults/SearchResults';
import { DownloadIcon, SearchIcon } from '../../components/Icon/Icon';
import type { SearchResultItem } from '../../_fixtures/search';

const LIBRARY_ONLY = new Set<JobType>(['retag_library', 'fetch_lyrics', 'fetch_art']);

export interface AddScreenProps {
  onSubmit?: (type: JobType, url: string) => void;
  onSearch?: (query: string, type: 'album' | 'track' | 'artist') => void;
  searchResults?: SearchResultItem[];
  searchLoading?: boolean;
  searchError?: string;
  msgText?: string;
  msgVariant?: 'ok' | 'err';
  msgVisible?: boolean;
}

export function AddScreen({ onSubmit, onSearch, searchResults = [], searchLoading, searchError, msgText, msgVariant, msgVisible }: AddScreenProps) {
  const [mode, setMode]               = useState<JobType>('track');
  const [url, setUrl]                 = useState('');
  const [libraryScan, setLibraryScan] = useState(false);
  const [searchOpen, setSearchOpen]   = useState(false);
  const [searchQ, setSearchQ]         = useState('');
  const [searchType, setSearchType]   = useState<'album' | 'track' | 'artist'>('album');

  const isLibraryOnly = LIBRARY_ONLY.has(mode);
  const isExplicit    = mode === 'explicit_upgrade';
  const urlRequired   = !isLibraryOnly && !(isExplicit && libraryScan);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const finalUrl = isLibraryOnly ? 'library' : (isExplicit && libraryScan ? 'library' : url);
    onSubmit?.(mode, finalUrl);
  };

  return (
    <>
      {/* Search panel */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
        <Button variant="ghost" style={{ fontSize: 11 }} onClick={() => setSearchOpen(p => !p)}>
          <SearchIcon size={13} /> Search Qobuz
        </Button>
      </div>

      {searchOpen && (
        <Card style={{ marginBottom: 16 }}>
          <div className="field-label" style={{ marginBottom: 8 }}><span>search qobuz</span></div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
            <input
              type="search"
              placeholder="Artist, album or track…"
              style={{ flex: 1 }}
              value={searchQ}
              onChange={e => { setSearchQ(e.target.value); onSearch?.(e.target.value, searchType); }}
            />
            <select
              style={{ width: 120 }}
              value={searchType}
              onChange={e => setSearchType(e.target.value as typeof searchType)}
            >
              <option value="album">Albums</option>
              <option value="track">Tracks</option>
              <option value="artist">Artists</option>
            </select>
          </div>
          <SearchResults results={searchResults} loading={searchLoading} error={searchError} />
        </Card>
      )}

      <SectionHead title="Add download" num="01" tag="new download" />

      <Card>
        <Field label="download mode" required style={{ marginBottom: 20 }}>
          <ModeGrid active={mode} onChange={m => { setMode(m); setUrl(''); setLibraryScan(false); }} />
        </Field>

        <form onSubmit={handleSubmit}>
          {!isLibraryOnly && (
            <Field label="qobuz url" required={urlRequired} labelRight="paste full link">
              <input
                type="url"
                placeholder={`https://play.qobuz.com/${mode === 'track' ? 'track' : mode === 'album' ? 'album' : 'playlist'}/…`}
                value={url}
                onChange={e => setUrl(e.target.value)}
                required={urlRequired}
                disabled={isExplicit && libraryScan}
              />
            </Field>
          )}

          {isExplicit && (
            <Field label="scan library instead">
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={libraryScan}
                  onChange={e => setLibraryScan(e.target.checked)}
                />
                <span>scan my /music library instead of a playlist</span>
              </label>
            </Field>
          )}

          <ButtonRow>
            <Button type="submit" variant="primary" icon={<DownloadIcon />}>Download</Button>
            <Msg text={msgText} variant={msgVariant} visible={msgVisible} />
          </ButtonRow>
        </form>
      </Card>
    </>
  );
}
