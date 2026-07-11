interface ErrorStateProps {
  title: string;
  message: string;
  suggestion?: string;
  onRetry?: () => void;
}

const ERROR_SUGGESTIONS: Record<string, string> = {
  '400': '请检查输入的题目是否为空或包含非法字符',
  '404': '该研究记录不存在，可能已被清理',
  '429': 'API 调用频率过高，请稍后重试',
  '500': '服务器内部错误，请查看后端日志',
  'timeout': '请求超时，可能是 LLM 或外部 API 响应慢，请重试',
  'network': '网络连接失败，请确认后端服务是否在运行',
};

export function getErrorSuggestion(errorText: string): string {
  for (const [code, suggestion] of Object.entries(ERROR_SUGGESTIONS)) {
    if (errorText.includes(code)) return suggestion;
  }
  return '请稍后重试，或检查后端服务是否正常运行';
}

export function ErrorState({ title, message, suggestion, onRetry }: ErrorStateProps) {
  const autoSuggestion = suggestion || getErrorSuggestion(message);
  return (
    <div className="error-state">
      <div className="error-icon">⚠️</div>
      <div className="error-title">{title}</div>
      <div className="error-message">{message}</div>
      <div className="error-suggestion">💡 {autoSuggestion}</div>
      {onRetry && (
        <button className="btn-secondary" onClick={onRetry}>重试</button>
      )}
    </div>
  );
}
