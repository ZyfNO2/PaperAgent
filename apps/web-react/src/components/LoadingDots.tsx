export function LoadingDots({ text = '正在分析' }: { text?: string }) {
  return (
    <span className="loading-dots">
      <span>{text}</span>
      <span className="dots">
        <span className="dot"></span>
        <span className="dot"></span>
        <span className="dot"></span>
      </span>
    </span>
  );
}
