import { useState } from "react";

function Chat({ messages, isLoading, onSendMessage }) {
  const [input, setInput] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!input.trim() || isLoading) {
      return;
    }

    const message = input;
    setInput("");
    await onSendMessage(message);
  };

  return (
    <div className="flex h-full flex-col bg-ink text-sand">
      <div className="border-b border-white/10 px-6 py-6 md:px-8">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-clay">AI Assistant</p>
        <h2 className="mt-3 font-display text-4xl text-white">Natural Language Capture</h2>
        <p className="mt-3 max-w-xl text-sm leading-6 text-sand/75">
          Type what happened in plain English. The parser will extract the key fields and update
          the form automatically.
        </p>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-6 py-6 md:px-8">
        {messages.map((message, index) => {
          const isUser = message.role === "user";

          return (
            <div
              key={`${message.role}-${index}`}
              className={`max-w-[85%] rounded-3xl px-4 py-3 text-sm leading-6 ${
                isUser ? "ml-auto bg-rose text-white" : "bg-white/10 text-sand"
              }`}
            >
              {message.content}
            </div>
          );
        })}

        {isLoading && (
          <div className="max-w-[85%] rounded-3xl bg-white/10 px-4 py-3 text-sm text-sand">
            Parsing your interaction...
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="border-t border-white/10 p-6 md:p-8">
        <div className="flex flex-col gap-3">
          <textarea
            className="min-h-28 w-full resize-none rounded-3xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none transition focus:border-clay focus:ring-4 focus:ring-clay/10"
            placeholder="Example: Met Dr Smith yesterday at 7 PM and discussed product efficacy. Shared trial summary handout."
            value={input}
            onChange={(event) => setInput(event.target.value)}
          />
          <button
            className="inline-flex items-center justify-center rounded-full bg-clay px-5 py-3 text-sm font-semibold text-ink transition hover:bg-sand disabled:cursor-not-allowed disabled:opacity-60"
            type="submit"
            disabled={isLoading || !input.trim()}
          >
            {isLoading ? "Parsing..." : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}

export default Chat;
