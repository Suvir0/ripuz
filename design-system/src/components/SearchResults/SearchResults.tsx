import React from 'react';
import type { SearchResultItem } from '../../_fixtures/search';
import { SearchResult } from '../SearchResult/SearchResult';

export interface SearchResultsProps {
  results: SearchResultItem[];
  loading?: boolean;
  error?: string;
  onQueue?: (url: string, type: string) => void;
}

export function SearchResults({ results, loading, error, onQueue }: SearchResultsProps) {
  if (loading) return <span style={{ color: 'var(--muted)', fontSize: 12 }}>Searching…</span>;
  if (error)   return <span style={{ color: 'var(--error)', fontSize: 12 }}>{error}</span>;
  if (!results.length) return <span style={{ color: 'var(--muted)', fontSize: 12 }}>No results</span>;
  return (
    <>
      {results.map(r => <SearchResult key={r.url} result={r} onQueue={onQueue} />)}
    </>
  );
}
