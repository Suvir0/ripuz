import React from 'react';
import type { Job } from '../../_fixtures/jobs';
import { SectionHead } from '../../components/SectionHead/SectionHead';
import { JobsList } from '../../components/JobsList/JobsList';
import { Modal } from '../../components/Modal/Modal';
import { LogViewer } from '../../components/LogViewer/LogViewer';

export interface JobsScreenProps {
  jobs: Job[];
  onRefresh?: () => void;
  onConfirm?: (id: number) => void;
  onCancel?: (id: number) => void;
  onDelete?: (id: number) => void;
  /** Controlled log modal */
  logJob?: Job & { log?: string };
  onCloseLog?: () => void;
  onLogOpen?: (id: number) => void;
}

export function JobsScreen({ jobs, onRefresh, onConfirm, onCancel, onDelete, logJob, onCloseLog, onLogOpen }: JobsScreenProps) {
  return (
    <>
      <SectionHead title="Jobs" num="02" tag="queue & history" />
      <JobsList
        jobs={jobs}
        onRefresh={onRefresh}
        onLog={onLogOpen}
        onConfirm={onConfirm}
        onCancel={onCancel}
        onDelete={onDelete}
      />
      {logJob && (
        <Modal
          open={!!logJob}
          title={`Job #${String(logJob.id).padStart(3, '0')} log`}
          subtitle={`${logJob.type} · ${logJob.status}`}
          onClose={onCloseLog}
          actions={
            logJob.status === 'awaiting_confirm' ? (
              <>
                <button className="btn-confirm" onClick={() => onConfirm?.(logJob.id)}>Confirm download</button>
                <button className="btn-cancel-job" onClick={() => onCancel?.(logJob.id)}>Cancel job</button>
              </>
            ) : undefined
          }
        >
          <LogViewer log={logJob.log ?? ''} />
        </Modal>
      )}
    </>
  );
}
