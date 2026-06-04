import { useCallback, useEffect, useRef, useState } from "react";

// Minimal typings for the Web Speech API — TS doesn't ship them by default.
type SRConstructor = new () => SRInstance;
interface SRInstance extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((ev: SRResultEvent) => void) | null;
  onerror: ((ev: SRErrorEvent) => void) | null;
  onend: (() => void) | null;
}
interface SRResultEvent {
  resultIndex: number;
  results: {
    length: number;
    [i: number]: {
      isFinal: boolean;
      0: { transcript: string };
    };
  };
}
interface SRErrorEvent {
  error: string;
}

function getCtor(): SRConstructor | null {
  const w = window as unknown as {
    SpeechRecognition?: SRConstructor;
    webkitSpeechRecognition?: SRConstructor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export interface SpeechRecognitionHook {
  supported: boolean;
  listening: boolean;
  // Finalised text from this session (committed phrases).
  finalText: string;
  // Live partial transcript — replaced on every interim result.
  interimText: string;
  error: string | null;
  start: () => void;
  stop: () => void;
  reset: () => void;
}

export function useSpeechRecognition(lang = "en-US"): SpeechRecognitionHook {
  const ctorRef = useRef<SRConstructor | null>(null);
  const recRef = useRef<SRInstance | null>(null);
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [finalText, setFinalText] = useState("");
  const [interimText, setInterimText] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctor = getCtor();
    ctorRef.current = ctor;
    setSupported(!!ctor);
  }, []);

  const reset = useCallback(() => {
    setFinalText("");
    setInterimText("");
    setError(null);
  }, []);

  const start = useCallback(() => {
    const Ctor = ctorRef.current;
    if (!Ctor) return;
    // Re-create per session — some browsers leak state across start/stop cycles.
    const rec = new Ctor();
    rec.lang = lang;
    rec.continuous = true;
    rec.interimResults = true;

    rec.onresult = (ev) => {
      let interim = "";
      let final = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const r = ev.results[i];
        const chunk = r[0].transcript;
        if (r.isFinal) final += chunk;
        else interim += chunk;
      }
      if (final) {
        setFinalText((prev) => (prev ? prev + " " : "") + final.trim());
      }
      setInterimText(interim);
    };
    rec.onerror = (ev) => {
      setError(ev.error || "speech recognition error");
      setListening(false);
    };
    rec.onend = () => {
      setListening(false);
      setInterimText("");
    };

    recRef.current = rec;
    setError(null);
    setInterimText("");
    setFinalText("");
    try {
      rec.start();
      setListening(true);
    } catch (e) {
      setError(String(e));
      setListening(false);
    }
  }, [lang]);

  const stop = useCallback(() => {
    const rec = recRef.current;
    if (!rec) return;
    try {
      rec.stop();
    } catch {
      /* noop */
    }
  }, []);

  // Tear down on unmount.
  useEffect(() => {
    return () => {
      const rec = recRef.current;
      if (rec) {
        try {
          rec.abort();
        } catch {
          /* noop */
        }
      }
    };
  }, []);

  return { supported, listening, finalText, interimText, error, start, stop, reset };
}
