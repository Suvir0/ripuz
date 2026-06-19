import React, { useEffect } from 'react';
import { CloseIcon } from '../Icon/Icon';

export interface ModalProps {
  open: boolean;
  title: string;
  subtitle?: string;
  /** Shown in the blue info bar above body (awaiting_confirm plan text) */
  planText?: string;
  /** Action buttons shown below plan bar */
  actions?: React.ReactNode;
  children: React.ReactNode;
  onClose?: () => void;
}

export function Modal({ open, title, subtitle, planText, actions, children, onClose }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose?.(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  return (
    <div
      className={`modal${open ? '' : ' modal--hidden'}`}
      role="dialog"
      aria-modal="true"
      onClick={(e) => { if (e.currentTarget === e.target) onClose?.(); }}
    >
      <div className="modal-inner">
        <div className="modal-head">
          <div className="modal-head-left">
            <h3>{title}</h3>
            {subtitle && <span className="modal-tag">{subtitle}</span>}
          </div>
          <button className="modal-close" aria-label="Close" onClick={onClose}>
            <CloseIcon />
          </button>
        </div>

        {planText && <div className="modal-plan-bar">{planText}</div>}
        {actions && <div className="modal-actions">{actions}</div>}

        <div className="modal-body">
          {children}
        </div>
      </div>
    </div>
  );
}
