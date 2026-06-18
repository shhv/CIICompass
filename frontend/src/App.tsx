import { useState } from "react";
import { ChatWindow } from "./components/ChatWindow";
import { Sidebar } from "./components/Sidebar";

export default function App() {
  const [open, setOpen] = useState<boolean>(() => {
    try {
      return localStorage.getItem("cii.sidebar") === "1";
    } catch {
      return false;
    }
  });
  const [product, setProduct] = useState<"cii" | "duo">(() => {
    try {
      const stored = localStorage.getItem("cii.product");
      return stored === "duo" ? "duo" : "cii";
    } catch {
      return "cii";
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
  const switchProduct = (p: "cii" | "duo") => {
    setProduct(p);
    try {
      localStorage.setItem("cii.product", p);
    } catch {
      // ignore
    }
  };
  return (
    <div className="flex h-full">
      <Sidebar open={open} onToggle={toggle} onNewChat={clearChat ?? undefined} product={product} onProductChange={switchProduct} />
      <main className="flex-1 min-w-0">
        <ChatWindow onClearReady={(fn) => setClearChat(() => fn)} product={product} />
      </main>
    </div>
  );
}
