import { Suspense, type ReactNode } from "react";
import { Link } from "react-router-dom";
import SettingsDialog from "./SettingsDialog";
import Sidebar from "./Sidebar";
import { useShell } from "./shell";
import { Button, Sheet, Tooltip } from "./ui";

/**
 * App frame (todo.md CL1): a collapsible sidebar, the page, and a Settings gear on every page. At phone width
 * the sidebar becomes a drawer. The preview panel belongs to the chat page, which sits inside `children`.
 */
export default function ChatShell({ children }: { children: ReactNode }) {
  const { isDesktop, sidebarOpen, toggleSidebar, closeDrawer, settingsOpen, setSettingsOpen } = useShell();
  return (
    <div className="flex h-full min-h-0">
      {isDesktop && sidebarOpen && (
        <aside aria-label="Chats" className="w-80 shrink-0 border-r border-line bg-surface">
          <Sidebar />
        </aside>
      )}
      {!isDesktop && (
        <Sheet open={sidebarOpen} onOpenChange={(o) => !o && closeDrawer()} title="Chats">
          <Sidebar onNavigate={closeDrawer} />
        </Sheet>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 border-b border-line px-3 py-2">
          <Tooltip
            trigger={
              <Button
                variant="ghost"
                size="sm"
                onClick={toggleSidebar}
                aria-label={sidebarOpen ? "Hide chats" : "Show chats"}
                aria-expanded={sidebarOpen}
              >
                <span aria-hidden>☰</span>
              </Button>
            }
          >
            {sidebarOpen ? "Hide chats" : "Show chats"}
          </Tooltip>
          <Link to="/" className="rounded-md px-1 font-semibold tracking-wide text-ink">
            OWL
          </Link>
          <span className="hidden text-xs text-muted sm:inline">Agentic research on Singapore data</span>
          <Button variant="ghost" size="sm" className="ml-auto" onClick={() => setSettingsOpen(true)} aria-label="Settings">
            <span aria-hidden>⚙</span>
          </Button>
        </header>
        <main className="min-h-0 flex-1">
          <Suspense fallback={<p className="p-4 text-sm text-muted">Loading…</p>}>{children}</Suspense>
        </main>
      </div>
      <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
    </div>
  );
}
