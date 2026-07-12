import type { ButtonHTMLAttributes, ReactNode } from 'react';

type Variant = 'primary' | 'secondary';
type Size = 'sm' | 'md';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  children: ReactNode;
}

const variantClass: Record<Variant, string> = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
};

const sizeStyle: Record<Size, React.CSSProperties> = {
  sm: { padding: '6px 14px', fontSize: '13px' },
  md: { padding: '10px 20px', fontSize: '14px' },
};

/**
 * 通用按钮组件。
 * variant=primary 用 .btn-primary（实色），variant=secondary 用 .btn-secondary（描边）。
 */
export function Button({
  variant = 'primary',
  size = 'md',
  children,
  className,
  style,
  ...rest
}: ButtonProps) {
  const mergedClassName = [variantClass[variant], className].filter(Boolean).join(' ');
  return (
    <button
      className={mergedClassName}
      style={{ ...sizeStyle[size], ...style }}
      {...rest}
    >
      {children}
    </button>
  );
}
