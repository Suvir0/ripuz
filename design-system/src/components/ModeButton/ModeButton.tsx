import React from 'react';
import type { JobType } from '../../_fixtures/jobs';
import { TYPE_ICONS, TYPE_LABELS } from '../Icon/Icon';

export const MODE_DESCS: Record<JobType, string> = {
  track:                'One track URL',
  album:                'Full album URL',
  discography:          'Artist URL → all albums',
  playlist:             'Tracks as listed',
  expand_albums:        'Expand each track to its full album',
  expand_discographies: 'Expand each artist to their full catalog',
  explicit_upgrade:     'Replace clean tracks with explicit versions',
  retag_library:        'Scan /music & tag untagged files with Picard',
  fetch_lyrics:         'Scan /music & download missing .lrc lyrics',
  fetch_art:            'Scan /music & download missing cover.jpg',
};

export interface ModeButtonProps {
  mode: JobType;
  active?: boolean;
  onClick?: () => void;
}

export function ModeButton({ mode, active = false, onClick }: ModeButtonProps) {
  const IconComp = TYPE_ICONS[mode];
  const label = TYPE_LABELS[mode] ?? mode;
  const desc = MODE_DESCS[mode] ?? '';
  return (
    <button
      type="button"
      className={`mode-btn${active ? ' mode-btn--active' : ''}`}
      onClick={onClick}
    >
      <span className="mode-btn__icon">{IconComp && <IconComp />}</span>
      <span className="mode-btn__label">{label}</span>
      <span className="mode-btn__desc">{desc}</span>
    </button>
  );
}
