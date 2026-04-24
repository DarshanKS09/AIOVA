import { useEffect, useRef, useState } from "react";

function Chat({ messages, isLoading, onSendMessage }) {
  const [input, setInput] = useState("");
  const [voiceState, setVoiceState] = useState("idle");
  const [voicePreview, setVoicePreview] = useState("");
  const [voiceError, setVoiceError] = useState("");
  const recognitionRef = useRef(null);
  const voiceStateRef = useRef("idle");
  const errorTimeoutRef = useRef(null);

  const clearVoiceErrorSoon = () => {
    if (errorTimeoutRef.current) {
      clearTimeout(errorTimeoutRef.current);
    }

    errorTimeoutRef.current = setTimeout(() => {
      setVoiceError("");
    }, 5000);
  };

  useEffect(() => {
    voiceStateRef.current = voiceState;
  }, [voiceState]);

  useEffect(() => {
    return () => {
      if (errorTimeoutRef.current) {
        clearTimeout(errorTimeoutRef.current);
      }
      recognitionRef.current?.stop();
    };
  }, []);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!input.trim() || isLoading) {
      return;
    }

    const message = input;
    setInput("");
    setVoiceError("");
    await onSendMessage(message);
  };

  const handleVoiceClick = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const isSecureOrigin =
      window.isSecureContext ||
      window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1";

    if (!SpeechRecognition) {
      setVoiceError("Voice input is not supported in this browser.");
      clearVoiceErrorSoon();
      return;
    }

    if (!isSecureOrigin) {
      setVoiceError("Voice input requires HTTPS or localhost in this browser.");
      clearVoiceErrorSoon();
      return;
    }

    if (voiceState === "listening" || voiceState === "processing") {
      recognitionRef.current?.stop();
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognitionRef.current = recognition;
    setVoiceError("");
    setVoicePreview("");
    setVoiceState("listening");

    recognition.onresult = async (event) => {
      const transcript = event.results?.[0]?.[0]?.transcript?.trim() || "";

      if (!transcript) {
        setVoiceState("idle");
        setVoiceError("No speech was detected. Try again.");
        clearVoiceErrorSoon();
        return;
      }

      setVoicePreview(transcript);
      setInput(transcript);
      setVoiceState("processing");

      try {
        await onSendMessage(transcript);
        setInput("");
      } finally {
        setVoiceState("idle");
      }
    };

    recognition.onerror = (event) => {
      const errorMessages = {
        "audio-capture": "No microphone was found on this device.",
        "not-allowed": "Microphone access was denied.",
        "no-speech": "No speech was detected. Try again.",
        aborted: "Voice input was cancelled.",
        network:
          "Voice recognition is unavailable right now. Try again, use Chrome on HTTPS or localhost, or type your update.",
        "service-not-allowed": "Voice input is blocked in this browser session.",
      };

      setVoiceState("idle");
      setVoicePreview("");
      setVoiceError(errorMessages[event.error] || "Voice input could not be completed.");
      clearVoiceErrorSoon();
    };

    recognition.onend = () => {
      if (voiceStateRef.current !== "processing") {
        setVoiceState("idle");
      }
      recognitionRef.current = null;
    };

    try {
      recognition.start();
    } catch {
      setVoiceState("idle");
      setVoiceError("Voice input could not be started. Try again.");
      clearVoiceErrorSoon();
      recognitionRef.current = null;
    }
  };

  const voiceLabel =
    voiceState === "listening"
      ? "Listening..."
      : voiceState === "processing"
        ? "Processing voice input..."
        : "Click the microphone to speak";

  return (
    <div className="flex h-full flex-col bg-white text-slate-800">
      <div className="border-b border-slate-200 px-5 py-5 md:px-6">
        <div className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm">
          <span
            className="inline-flex h-5 w-5 items-center justify-center rounded bg-white/15"
            aria-hidden="true"
          >
            <svg
              viewBox="0 0 24 24"
              className="h-3.5 w-3.5"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 3v3" />
              <rect x="6" y="8" width="12" height="9" rx="2" />
              <path d="M9 17v2" />
              <path d="M15 17v2" />
              <path d="M8 12h.01" />
              <path d="M16 12h.01" />
              <path d="M9.5 14.5h5" />
            </svg>
          </span>
          AI Assistant
        </div>
        <p className="mt-2 text-sm text-slate-500">Log interaction details here via chat</p>
      </div>

      <div className="flex-1 overflow-y-auto bg-slate-50 px-5 py-6 md:px-6">
        <div className="mb-4 rounded-[12px] border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <p className="text-sm font-medium text-slate-700">{voiceLabel}</p>
          {voicePreview ? (
            <p className="mt-1 text-sm text-slate-500">Heard: "{voicePreview}"</p>
          ) : null}
          {voiceError ? <p className="mt-1 text-sm text-rose-600">{voiceError}</p> : null}
        </div>

        <div className="space-y-4">
          {messages.map((message, index) => {
            const isUser = message.role === "user";

            return (
              <div
                key={`${message.role}-${index}`}
                className={`max-w-[88%] rounded-[12px] border px-4 py-3 text-sm leading-6 shadow-sm ${
                  isUser
                    ? "ml-auto border-blue-200 bg-blue-600 text-white"
                    : "border-cyan-100 bg-cyan-50 text-slate-700"
                }`}
              >
                {message.content}
              </div>
            );
          })}
        </div>

        {isLoading && (
          <div className="mt-4 max-w-[88%] rounded-[12px] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">
            Parsing your interaction...
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="border-t border-slate-200 bg-white p-5 md:p-6">
        <div className="flex items-end gap-3">
          <button
            type="button"
            onClick={handleVoiceClick}
            className={`inline-flex min-h-[52px] min-w-[52px] items-center justify-center rounded-[14px] border text-sm font-semibold transition ${
              voiceState === "listening"
                ? "border-rose-200 bg-rose-50 text-rose-600"
                : voiceState === "processing"
                  ? "border-amber-200 bg-amber-50 text-amber-600"
                  : "border-slate-200 bg-white text-slate-600 hover:border-blue-300 hover:text-blue-600"
            } disabled:cursor-not-allowed disabled:opacity-60`}
            disabled={isLoading || voiceState === "processing"}
            aria-label="Use microphone"
            title="Use microphone"
          >
            {voiceState === "processing" ? "..." : "Mic"}
          </button>
          <textarea
            className="min-h-[52px] w-full resize-none rounded-[12px] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
            placeholder="Describe Interaction..."
            value={input}
            onChange={(event) => setInput(event.target.value)}
          />
          <button
            className="inline-flex min-h-[52px] min-w-[82px] items-center justify-center rounded-[18px] bg-blue-600 px-5 py-3 text-base font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            type="submit"
            disabled={isLoading || !input.trim()}
          >
            {isLoading ? "..." : "Log"}
          </button>
        </div>
      </form>
    </div>
  );
}

export default Chat;
