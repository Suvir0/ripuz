import React from 'react';
import type { Job } from '../../_fixtures/jobs';
import { Pill } from '../Pill/Pill';
import { TYPE_ICONS, TYPE_LABELS } from '../Icon/Icon';

const ACTIVE_STATUSES = new Set([
  'queued', 'resolving', 'awaiting_confirm', 'confirmed',
  'downloading', 'tagging', 'verifying', 'cancelling',
]);
const CANCELLABLE_STATUSES = new Set([
  'queued', 'resolving', 'awaiting_confirm', 'confirmed',
  'downloading', 'tagging', 'verifying',
]);
const DELETABLE_STATUSES = new Set(['done', 'done_with_warnings', 'error', 'cancelled']);

function formatPlan(planJson?: string | null): string {
  if (!planJson) return '';
  try {
    const plan = JSON.parse(planJson);
    if (plan.missing_albums !== undefined)
      return `${plan.missing_albums || 0} of ${plan.scanned_albums || 0} album(s) missing cover art`;
    if (plan.missing_files !== undefined)
      return `${plan.missing_files || 0} of ${plan.scanned_files || 0} file(s) missing lyrics · ${plan.album_count || 0} album dir(s)`;
    if (plan.dirs !== undefined)
      return `${plan.album_count || 0} album dir(s) to retag · ${plan.untagged_files || 0} of ${plan.scanned_files || 0} file(s) untagged`;
    const albums = plan.albums || [];
    const skipped = plan.skipped_existing || 0;
    const dup = plan.skipped_duplicate || 0;
    const est = plan.est_gb || 0;
    const capped = plan.capped ? ` · capped at ${plan.cap}` : '';
    const dupMsg = dup > 0 ? ` · ${dup} claimed by other job(s)` : '';
    return `${albums.length} album(s) to download${capped} · ${skipped} already present${dupMsg} · ~${est} GB`;
  } catch {
    return '';
  }
}

export interface JobCardProps {
  job: Job;
  onLog?: (id: number) => void;
  onConfirm?: (id: number) => void;
  onCancel?: (id: number) => void;
  onDelete?: (id: number) => void;
}

export function JobCard({ job, onLog, onConfirm, onCancel, onDelete }: JobCardProps) {
  const isReview = job.status === 'awaiting_confirm';
  const isCancellable = CANCELLABLE_STATUSES.has(job.status);
  const isDeletable = DELETABLE_STATUSES.has(job.status);
  const planSummary = isReview ? formatPlan(job.plan) : '';
  const label = TYPE_LABELS[job.type] ?? job.type;
  const IconComp = TYPE_ICONS[job.type];

  return (
    <div className={`job-card${isReview ? ' job-card--review' : ''}`}>
      <div className="job-num">#{String(job.id).padStart(3, '0')}</div>
      <div className="job-main">
        <div className="job-title">
          {IconComp && <IconComp size={13} />}
          {label}
        </div>
        <div className="job-url">{job.url}</div>
        <div className="job-meta"><span>{job.created_at}</span></div>
      </div>

      <Pill status={job.status} />

      {!isReview && isCancellable && (
        <button className="job-action-btn" onClick={() => onCancel?.(job.id)} title="Cancel job">✕</button>
      )}
      {isDeletable && (
        <button className="job-action-btn" onClick={() => onDelete?.(job.id)} title="Delete job">🗑</button>
      )}
      <button className="job-log-btn" onClick={() => onLog?.(job.id)}>Log</button>

      {isReview && (
        <div className="job-confirm-row">
          <span className="job-plan-summary">{planSummary}</span>
          <div className="job-confirm-btns">
            <button className="btn-confirm" onClick={() => onConfirm?.(job.id)}>Confirm download</button>
            <button className="btn-cancel-job" onClick={() => onCancel?.(job.id)}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}
