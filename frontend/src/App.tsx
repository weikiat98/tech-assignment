import { lazy } from "react";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import ChatShell from "./components/ChatShell";
import TokenGate from "./components/TokenGate";
import { ShellProvider } from "./components/shell";
import { api } from "./lib/api";
import Home from "./pages/Home";
// The chat page (answers, charts, preview) loads on demand so the first screen stays small.
const Chat = lazy(() => import("./pages/Chat"));

/** Links to a single run (`/analyses/:id`, from before chats existed) open the chat that holds it. */
function LegacyRun() {
  const { id } = useParams<{ id: string }>();
  const { data, error } = useQuery({ queryKey: ["analysis", id], queryFn: () => api.getAnalysis(id!) });
  if (error) return <Navigate to="/" replace />;
  if (!data) return <p className="p-4 text-sm text-muted">Loading…</p>;
  return <Navigate to={data.chat_id ? `/chats/${data.chat_id}` : "/"} replace />;
}

export default function App() {
  return (
    <TokenGate>
      <ShellProvider>
        <ChatShell>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/chats/:id" element={<Chat />} />
            <Route path="/analyses/:id" element={<LegacyRun />} />
            <Route path="/history" element={<Navigate to="/" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </ChatShell>
      </ShellProvider>
    </TokenGate>
  );
}
