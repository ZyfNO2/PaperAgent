import { Link, useLocation } from 'react-router-dom';

export function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const isActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(path + '/');

  return (
    <div>
      <nav className="navbar" aria-label="主导航">
        <Link to="/" className="navbar-brand">PaperAgent</Link>
        <div className="navbar-links">
          <Link to="/" className={isActive('/') && location.pathname === '/' ? 'active' : ''}>首页</Link>
          <Link to="/workbench" className={isActive('/workbench') ? 'active' : ''}>工作台</Link>
          <Link to="/rag" className={isActive('/rag') ? 'active' : 'disabled'}>RAG</Link>
          <Link to="/settings" className={isActive('/settings') ? 'active' : ''}>Settings</Link>
        </div>
      </nav>
      <div className="container">{children}</div>
    </div>
  );
}
