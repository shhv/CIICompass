import { ChatWindow } from "./components/ChatWindow";
import { Sidebar } from "./components/Sidebar";

export default function App() {
  return (
    <div className="flex h-full">
      <Sidebar />
      <main className="flex-1 min-w-0">
        <ChatWindow />
      </main>
    </div>
  );
}
