import React from 'react';
import type { JobStatus } from '../../_fixtures/jobs';

export type PillVariant = 'queued' | 'running' | 'tagging' | 'done' | 'warn' | 'error' | 'review' | 'cancelled';

const STATUS_MAP: Record<JobStatus, { label: string; variant: PillVariant }> = {
  queued:             { label: 'queued',      variant: 'queued'    },
  resolving:          { label: 'resolving',   variant: 'running'   },
  awaiting_confirm:   { label: 'review',      variant: 'review'    },
  confirmed:          { label: 'confirmed',   variant: 'queued'    },
  downloading:        { label: 'downloading', variant: 'running'   },
  tagging:            { label: 'tagging',     variant: 'tagging'   },
  verifying:          { label: 'verifying',   variant: 'tagging'   },
  cancelling:         { label: 'cancelling',  variant: 'error'     },
  cancelled:          { label: 'cancelled',   variant: 'cancelled' },
  done:               { label: 'done',        variant: 'done'      },
  done_with_warnings: { label: 'done · warn', variant: 'warn'      },
  error:              { label: 'error',       variant: 'error'     },
};

export interface PillProps {
  status: JobStatus;
}

export function Pill({ status }: PillProps) {
  const { label, variant } = STATUS_MAP[status] ?? { label: status, variant: 'queued' as PillVariant };
  return <span className={`pill pill--${variant}`}>{label}</span>;
}
