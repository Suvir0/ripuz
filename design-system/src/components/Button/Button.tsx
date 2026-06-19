import React from 'react';

export type ButtonVariant = 'default' | 'primary' | 'ghost';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  icon?: React.ReactNode;
  children: React.ReactNode;
}

export function Button({
  variant = 'default',
  icon,
  children,
  className = '',
  ...rest
}: ButtonProps) {
  const variantClass = variant === 'default' ? '' : `btn--${variant}`;
  return (
    <button className={`btn ${variantClass} ${className}`.trim()} {...rest}>
      {icon}
      {children}
    </button>
  );
}

export function ButtonRow({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`btn-row ${className}`.trim()}>{children}</div>;
}
