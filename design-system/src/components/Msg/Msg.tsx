import React from 'react';

export type MsgVariant = 'ok' | 'err';

export interface MsgProps {
  text?: string;
  variant?: MsgVariant;
  visible?: boolean;
}

export function Msg({ text, variant = 'ok', visible = false }: MsgProps) {
  return (
    <span className={`msg msg--${variant}${visible ? ' msg--show' : ''}`}>
      {text}
    </span>
  );
}
