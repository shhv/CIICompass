import { useEffect, useRef, useState, KeyboardEvent, ClipboardEvent, ChangeEvent } from "react";
import { useSpeechRecognition } from "../lib/useSpeechRecognition";
import type { FileAttachment } from "../lib/api";

type PendingFile = {
  file: File;
  preview: string;
  attachment: FileAttachment;
};

const MAX_FILES = 4;
const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20MB

export function Composer({
  onSend,
  disabled,
}: {
  onSend: (text: string, files?: FileAttachment[]) => void;
  disabled?: boolean;
}) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState<PendingFile[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const speech = useSpeechRecognition();

  useEffect(() => {
    if (!speech.listening) return;
    const live = [speech.finalText, speech.interimText].filter(Boolean).join(" ");
    setText(live);
  }, [speech.listening, speech.finalText, speech.interimText]);

  const addFiles = async (fileList: FileList | File[]) => {
    const incoming = Array.from(fileList).slice(0, MAX_FILES - files.length);
    const newFiles: PendingFile[] = [];
    for (const file of incoming) {
      if (file.size > MAX_FILE_SIZE) continue;
      const data = await fileToBase64(file);
      const preview = file.type.startsWith("image/") ? URL.createObjectURL(file) : "";
      newFiles.push({
        file,
        preview,
        attachment: { filename: file.name, media_type: file.type || "application/octet-stream", data },
      });
    }
    setFiles((prev) => [...prev, ...newFiles].slice(0, MAX_FILES));
  };

  const removeFile = (idx: number) => {
    setFiles((prev) => {
      const copy = [...prev];
      if (copy[idx].preview) URL.revokeObjectURL(copy[idx].preview);
      copy.splice(idx, 1);
      return copy;
    });
  };

  const onPaste = (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    const imageFiles: File[] = [];
    for (const item of Array.from(items)) {
      if (item.kind === "file") {
        const f = item.getAsFile();
        if (f) imageFiles.push(f);
      }
    }
    if (imageFiles.length > 0) {
      e.preventDefault();
      addFiles(imageFiles);
    }
  };

  const onFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) addFiles(e.target.files);
    e.target.value = "";
  };

  const submit = () => {
    const t = text.trim();
    if ((!t && files.length === 0) || disabled) return;
    if (speech.listening) speech.stop();
    onSend(t || "(see attached file)", files.length > 0 ? files.map((f) => f.attachment) : undefined);
    files.forEach((f) => { if (f.preview) URL.revokeObjectURL(f.preview); });
    setFiles([]);
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
      <div className="max-w-4xl mx-auto">
        {files.length > 0 && (
          <div className="flex gap-2 mb-2 flex-wrap">
            {files.map((f, i) => (
              <div key={i} className="relative group">
                {f.preview ? (
                  <img src={f.preview} alt={f.file.name} className="h-14 w-14 object-cover rounded-lg border border-slate-200" />
                ) : (
                  <div className="h-14 w-auto min-w-[3.5rem] px-2 flex items-center justify-center rounded-lg border border-slate-200 bg-slate-50 text-xs text-slate-600 truncate max-w-[10rem]">
                    {f.file.name}
                  </div>
                )}
                <button
                  onClick={() => removeFile(i)}
                  className="absolute -top-1.5 -right-1.5 bg-red-500 text-white rounded-full w-5 h-5 text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition"
                >
                  &times;
                </button>
              </div>
            ))}
          </div>
        )}
        <div className="flex items-end rounded-2xl border border-slate-200 bg-slate-50 focus-within:ring-2 focus-within:ring-sky-500 focus-within:border-transparent transition shadow-sm">
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || files.length >= MAX_FILES}
            title="Attach file"
            aria-label="Attach file"
            className="flex-none p-3 text-slate-400 hover:text-slate-600 disabled:opacity-40 transition"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
            </svg>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,.pdf,.txt,.md,.py,.json,.yaml,.yml,.log,.csv,.xml,.html,.js,.ts,.sh"
            multiple
            onChange={onFileChange}
            className="hidden"
          />
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
            onPaste={onPaste}
            rows={2}
            placeholder={
              speech.listening
                ? "Listening… click the mic again to stop."
                : "Ask a question… (Enter to send, Shift+Enter for newline)"
            }
            className="flex-1 resize-none bg-transparent px-1 py-3 text-slate-900 placeholder:text-slate-400 focus:outline-none"
            disabled={disabled}
          />
          {speech.supported && (
            <button
              onClick={toggleMic}
              disabled={disabled}
              title={speech.listening ? "Stop recording" : "Speak"}
              aria-label={speech.listening ? "Stop recording" : "Start voice input"}
              className={`flex-none p-3 transition ${
                speech.listening
                  ? "text-red-500 animate-pulse"
                  : "text-slate-400 hover:text-slate-600"
              } disabled:opacity-40`}
            >
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
            disabled={disabled || (!text.trim() && files.length === 0)}
            className="flex-none p-3 text-sky-600 hover:text-sky-700 disabled:text-slate-300 transition"
            title="Send"
            aria-label="Send message"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
            </svg>
          </button>
        </div>
        {speech.error && (
          <div className="mt-2 text-xs text-red-600">
            Mic error: {speech.error}
          </div>
        )}
      </div>
    </div>
  );
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      resolve(result.split(",")[1]);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
