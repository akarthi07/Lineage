import { Link, useLocation } from "react-router-dom";

function NavLink({ to, children }) {
  const { pathname } = useLocation();
  const active = pathname === to;
  return (
    <Link
      to={to}
      className={`text-sm font-medium transition-colors duration-150 ${
        active ? "text-text-primary" : "text-text-secondary hover:text-text-primary"
      }`}
    >
      {children}
    </Link>
  );
}

export default function Layout({ children }) {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Nav */}
      <header className="fixed top-0 inset-x-0 z-50 h-14 border-b border-border/60 bg-bg/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 h-full flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-6 h-6 rounded-lg bg-purple flex items-center justify-center shadow-purple">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <circle cx="6" cy="2" r="1.5" fill="white" />
                <circle cx="2" cy="9" r="1.5" fill="white" />
                <circle cx="10" cy="9" r="1.5" fill="white" />
                <line x1="6" y1="2" x2="2" y2="9" stroke="white" strokeWidth="0.8" strokeOpacity="0.6" />
                <line x1="6" y1="2" x2="10" y2="9" stroke="white" strokeWidth="0.8" strokeOpacity="0.6" />
                <line x1="2" y1="9" x2="10" y2="9" stroke="white" strokeWidth="0.8" strokeOpacity="0.6" />
              </svg>
            </div>
            <span className="font-semibold text-sm tracking-tight text-text-primary">Lineage</span>
          </Link>

          <nav className="flex items-center gap-6">
            <NavLink to="/">Discover</NavLink>
            <NavLink to="/genesis">Genesis</NavLink>
          </nav>

          <div className="flex items-center gap-3">
            <span className="text-xs text-text-muted font-mono px-2 py-1 rounded-lg bg-elevated border border-border">
              Beta
            </span>
          </div>
        </div>
      </header>

      {/* Page content */}
      <main className="flex-1 pt-14">
        {children}
      </main>
    </div>
  );
}
