import type { ReactNode } from 'react';

interface CardProps {
  title?: string;
  testId?: string;
  children: ReactNode;
  className?: string;
}

/**
 * 通用卡片容器，复用 .report-section / .paper-list 的视觉风格。
 * title 存在时渲染标题行；否则只渲染内容。
 */
export function Card({ title, testId, children, className }: CardProps) {
  const wrapperClass = ['paper-list', className].filter(Boolean).join(' ');
  return (
    <div className={wrapperClass} data-testid={testId}>
      {title ? <h3>{title}</h3> : null}
      <div>{children}</div>
    </div>
  );
}
