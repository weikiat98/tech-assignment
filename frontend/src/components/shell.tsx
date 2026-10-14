import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

const SIDEBAR_KEY = "owl-sidebar-open";
const DESKTOP = "(min-width: 1024px)";

function readStored(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_KEY) !== "false";
  } catch {
    return true;
  }
}

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => (typeof window.matchMedia === "function" ? window.matchMedia(query).matches : true));
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia(query);
    const on = () => setMatches(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [query]);
  return matches;
}

interface Shell {
  isDesktop: boolean;
  /** Desktop: is the sidebar column shown. Phone: is the drawer open. */
  sidebarOpen: boolean;
  /** A user's choice: remembered per browser on desktop. */
  toggleSidebar: () => void;
  closeDrawer: () => void;
  previewOpen: boolean;
  setPreviewOpen: (open: boolean) => void;
  settingsOpen: boolean;
  setSettingsOpen: (open: boolean) => void;
}

const Ctx = createContext<Shell | null>(null);

export function ShellProvider({ children }: { children: ReactNode }) {
  const isDesktop = useMediaQuery(DESKTOP);
  const [desktopOpen, setDesktopOpen] = useState(readStored);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [previewOpen, setPreviewOpenState] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const toggleSidebar = useCallback(() => {
    if (!isDesktop) return setDrawerOpen((o) => !o);
    setDesktopOpen((open) => {
      try {
        localStorage.setItem(SIDEBAR_KEY, String(!open));
      } catch {
        /* storage unavailable: the choice lasts for this page only */
      }
      return !open;
    });
  }, [isDesktop]);

  // Opening the preview makes room for it by collapsing the sidebar; that is not saved as the user's choice.
  const setPreviewOpen = useCallback(
    (open: boolean) => {
      setPreviewOpenState(open);
      if (open && isDesktop) setDesktopOpen(false);
    },
    [isDesktop],
  );

  const value = useMemo<Shell>(
    () => ({
      isDesktop,
      sidebarOpen: isDesktop ? desktopOpen : drawerOpen,
      toggleSidebar,
      closeDrawer: () => setDrawerOpen(false),
      previewOpen,
      setPreviewOpen,
      settingsOpen,
      setSettingsOpen,
    }),
    [isDesktop, desktopOpen, drawerOpen, toggleSidebar, previewOpen, setPreviewOpen, settingsOpen],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useShell(): Shell {
  const v = useContext(Ctx);
  if (!v) throw new Error("useShell must be used inside ShellProvider");
  return v;
}
