import { useState, KeyboardEvent } from "react";

export function Composer({
  onSend,
  disabled,
}: {
  onSend: (text: string) => void;
  disabled?: boolean;
}) {
  const [text, setText] = useState("");

  const submit = () => {
    const t = text.trim();
    if (!t || disabled) return;
    onSend(t);
    setText("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="border-t border-slate-800 bg-slate-950 p-3">
      <div className="flex gap-2 max-w-4xl mx-auto">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          rows={2}
          placeholder="Ask about CII docs… (Enter to send, Shift+Enter for newline)"
          className="flex-1 resize-none rounded-xl bg-slate-900 border border-slate-800 px-3 py-2 text-slate-100 focus:outline-none focus:ring-1 focus:ring-sky-600"
          disabled={disabled}
        />
        <button
          onClick={submit}
          disabled={disabled || !text.trim()}
          className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 disabled:bg-slate-700 disabled:text-slate-400 text-white"
        >
          Send
        </button>
      </div>
    </div>
  );
}
