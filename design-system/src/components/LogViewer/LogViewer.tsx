import React from 'react';

function colorClass(line: string): string {
  const low = line.toLowerCase();
  if (/error|failed|exception/.test(low)) return 'log-err';
  if (/warn|warning/.test(low)) return 'log-warn';
  if (/\[pipeline\]|\[pipeline\//.test(low)) return 'log-dim';
  return '';
}

export interface LogViewerProps {
  log: string;
}

export function LogViewer({ log }: LogViewerProps) {
  const lines = (log || '(no log yet)').split('\n');
  return (
    <pre className="log-viewer">
      {lines.map((line, i) => {
        const num = String(i + 1).padStart(2, '0');
        const cls = colorClass(line);
        return (
          <React.Fragment key={i}>
            <span className="log-num">{num}</span>
            <span className={cls || undefined}>{line}</span>
            {'\n'}
          </React.Fragment>
        );
      })}
    </pre>
  );
}
