import { useState } from "react";
import { ChatWindow } from "./components/ChatWindow";
import { Sidebar } from "./components/Sidebar";

export default function App() {
  const [open, setOpen] = useState<boolean>(() => {
    try {
      return localStorage.getItem("cii.sidebar") !== "0";
    } catch {
      return true;
    }
  });
  const [clearChat, setClearChat] = useState<(() => void) | null>(null);
  const toggle = () => {
    setOpen((v) => {
      const next = !v;
      try {
        localStorage.setItem("cii.sidebar", next ? "1" : "0");
      } catch {
        // ignore
      }
      return next;
    });
  };
  return (
    <div className="flex h-full">
      <Sidebar open={open} onToggle={toggle} onNewChat={clearChat ?? undefined} />
      <main className="flex-1 min-w-0">
        <ChatWindow onClearReady={(fn) => setClearChat(() => fn)} />
      </main>
    </div>
  );
}
