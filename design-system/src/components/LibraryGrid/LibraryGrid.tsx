import React from 'react';
import type { Album } from '../../_fixtures/library';
import { LibraryCard } from '../LibraryCard/LibraryCard';
import { Button } from '../Button/Button';
import { RefreshIcon } from '../Icon/Icon';

export interface LibraryGridProps {
  albums: Album[];
  onAlbumClick?: (id: string) => void;
  onRefresh?: () => void;
  hasMore?: boolean;
  remaining?: number;
  onLoadMore?: () => void;
  /** Toolbar search/sort slot */
  toolbar?: React.ReactNode;
}

export function LibraryGrid({ albums, onAlbumClick, onRefresh, hasMore, remaining, onLoadMore, toolbar }: LibraryGridProps) {
  return (
    <>
      <div className="jobs-toolbar" style={{ marginTop: 16 }}>
        {toolbar}
        <Button variant="ghost" icon={<RefreshIcon />} onClick={onRefresh}>Refresh</Button>
      </div>
      <div className="lib-grid">
        {albums.map(a => (
          <LibraryCard key={a.id} album={a} onClick={onAlbumClick} />
        ))}
      </div>
      {hasMore && (
        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <Button variant="ghost" onClick={onLoadMore}>Load more ({remaining} remaining)</Button>
        </div>
      )}
    </>
  );
}
