import { lazy, Suspense, type ReactNode } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import TokenGate from "./components/TokenGate";
import NewAnalysis from "./pages/NewAnalysis";
// Heavier routes load on demand so the first screen stays small.
const RunView = lazy(() => import("./pages/RunView"));
const History = lazy(() => import("./pages/History"));

function NavItem({ to, children }: { to: string; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        `rounded-md px-3 py-1.5 text-sm font-medium ${
          isActive ? "bg-white/15 text-white" : "text-slate-300 hover:text-white"
        }`
      }
    >
      {children}
    </NavLink>
  );
}

export default function App() {
  return (
    <div className="flex min-h-full flex-col">
      <header className="bg-slate-900">
        <div className="mx-auto flex max-w-[1500px] items-center gap-6 px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="grid h-7 w-7 place-items-center rounded-md bg-brand-600 text-sm font-bold text-white">PA</div>
            <span className="font-semibold text-white">Policy Analytics</span>
            <span className="hidden text-xs text-slate-400 sm:inline">agentic research for Singapore data</span>
          </div>
          <nav className="flex gap-1">
            <NavItem to="/">New analysis</NavItem>
            <NavItem to="/history">History</NavItem>
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1500px] flex-1 px-4 py-5">
        <TokenGate>
          <Suspense fallback={<p className="text-sm text-slate-500">Loading…</p>}>
          <Routes>
            <Route path="/" element={<NewAnalysis />} />
            <Route path="/analyses/:id" element={<RunView />} />
            <Route path="/history" element={<History />} />
          </Routes>
          </Suspense>
        </TokenGate>
      </main>
    </div>
  );
}
