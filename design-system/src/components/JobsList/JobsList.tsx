import React, { useState } from 'react';
import type { Job, JobStatus } from '../../_fixtures/jobs';
import { FilterTabs } from '../FilterTabs/FilterTabs';
import { JobCard } from '../JobCard/JobCard';
import { Empty } from '../Empty/Empty';
import { Button } from '../Button/Button';
import { RefreshIcon } from '../Icon/Icon';

type FilterKey = 'all' | 'active' | 'done' | 'error';

const ACTIVE_STATUSES = new Set<JobStatus>([
  'queued', 'resolving', 'awaiting_confirm', 'confirmed',
  'downloading', 'tagging', 'verifying', 'cancelling',
]);

const JOB_FILTERS = [
  { key: 'all',    label: 'All'    },
  { key: 'active', label: 'Active' },
  { key: 'done',   label: 'Done'   },
  { key: 'error',  label: 'Error'  },
];

function filterJobs(jobs: Job[], filter: FilterKey): Job[] {
  if (filter === 'active') return jobs.filter(j => ACTIVE_STATUSES.has(j.status));
  if (filter === 'done')   return jobs.filter(j => j.status === 'done' || j.status === 'done_with_warnings');
  if (filter === 'error')  return jobs.filter(j => j.status === 'error');
  return jobs;
}

export interface JobsListProps {
  jobs: Job[];
  onRefresh?: () => void;
  onLog?: (id: number) => void;
  onConfirm?: (id: number) => void;
  onCancel?: (id: number) => void;
  onDelete?: (id: number) => void;
}

export function JobsList({ jobs, onRefresh, onLog, onConfirm, onCancel, onDelete }: JobsListProps) {
  const [filter, setFilter] = useState<FilterKey>('all');
  const filtered = filterJobs(jobs, filter);

  return (
    <>
      <div className="jobs-toolbar">
        <FilterTabs items={JOB_FILTERS} active={filter} onChange={(k) => setFilter(k as FilterKey)} />
        <Button variant="ghost" icon={<RefreshIcon />} onClick={onRefresh}>Refresh</Button>
      </div>
      <div className="jobs-list">
        {filtered.length === 0 ? (
          <Empty label="no jobs">Paste a playlist URL on the <b>Add</b> tab to start a download.</Empty>
        ) : (
          filtered.map(job => (
            <JobCard
              key={job.id}
              job={job}
              onLog={onLog}
              onConfirm={onConfirm}
              onCancel={onCancel}
              onDelete={onDelete}
            />
          ))
        )}
      </div>
    </>
  );
}
