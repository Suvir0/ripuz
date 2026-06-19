import React from 'react';
import type { JobType } from '../../_fixtures/jobs';
import { ModeButton } from '../ModeButton/ModeButton';

const ALL_MODES: JobType[] = [
  'track', 'album', 'discography', 'playlist',
  'expand_albums', 'expand_discographies', 'explicit_upgrade',
  'retag_library', 'fetch_lyrics', 'fetch_art',
];

export interface ModeGridProps {
  active: JobType;
  onChange?: (mode: JobType) => void;
}

export function ModeGrid({ active, onChange }: ModeGridProps) {
  return (
    <div className="mode-grid">
      {ALL_MODES.map((mode) => (
        <ModeButton
          key={mode}
          mode={mode}
          active={active === mode}
          onClick={() => onChange?.(mode)}
        />
      ))}
    </div>
  );
}
