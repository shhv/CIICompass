import { useEffect, useState, KeyboardEvent } from "react";
import { useSpeechRecognition } from "../lib/useSpeechRecognition";

export function Composer({
  onSend,
  disabled,
}: {
  onSend: (text: string) => void;
  disabled?: boolean;
}) {
  const [text, setText] = useState("");
  const speech = useSpeechRecognition();

  // While listening, mirror the live transcript into the textarea so the
  // user sees what was heard. Final text + current interim string.
  useEffect(() => {
    if (!speech.listening) return;
    const live = [speech.finalText, speech.interimText].filter(Boolean).join(" ");
    setText(live);
  }, [speech.listening, speech.finalText, speech.interimText]);

  const submit = () => {
    const t = text.trim();
    if (!t || disabled) return;
    if (speech.listening) speech.stop();
    onSend(t);
    setText("");
    speech.reset();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const toggleMic = () => {
    if (speech.listening) speech.stop();
    else speech.start();
  };

  return (
    <div className="border-t border-slate-200 bg-white p-4">
      <div className="flex gap-3 max-w-4xl mx-auto items-end">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          rows={2}
          placeholder={
            speech.listening
              ? "Listening… click the mic again to stop."
              : "Ask about CII docs… (Enter to send, Shift+Enter for newline)"
          }
          className="flex-1 resize-none rounded-xl bg-slate-50 border border-slate-200 px-4 py-3 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent"
          disabled={disabled}
        />
        {speech.supported && (
          <button
            onClick={toggleMic}
            disabled={disabled}
            title={speech.listening ? "Stop recording" : "Speak"}
            aria-label={speech.listening ? "Stop recording" : "Start voice input"}
            className={`px-3 py-3 rounded-xl border transition shadow-sm ${
              speech.listening
                ? "bg-red-500 hover:bg-red-600 border-red-500 text-white animate-pulse"
                : "bg-white hover:bg-slate-50 border-slate-200 text-slate-600"
            } disabled:opacity-50`}
          >
            {/* Mic glyph */}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
          </button>
        )}
        <button
          onClick={submit}
          disabled={disabled || !text.trim()}
          className="px-5 py-3 rounded-xl bg-sky-600 hover:bg-sky-700 disabled:bg-slate-200 disabled:text-slate-400 text-white font-medium transition shadow-sm"
        >
          Send
        </button>
      </div>
      {speech.error && (
        <div className="max-w-4xl mx-auto mt-2 text-xs text-red-600">
          Mic error: {speech.error}
        </div>
      )}
    </div>
  );
}
