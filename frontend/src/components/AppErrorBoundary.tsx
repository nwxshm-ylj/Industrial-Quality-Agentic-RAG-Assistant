import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props { children: ReactNode }
interface State { hasError: boolean }

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("React workspace rendering failed", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="fatal-error">
          <span>WORKSPACE RECOVERY</span>
          <h1>页面加载失败</h1>
          <p>当前会话仍然安全，请刷新页面重试。如果问题持续，请记录时间并查看 API 与浏览器日志。</p>
          <button type="button" onClick={() => window.location.reload()}>刷新工作台</button>
        </main>
      );
    }
    return this.props.children;
  }
}
