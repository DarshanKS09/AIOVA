import { useState } from "react";
import axios from "axios";
import Form from "./components/Form";
import Chat from "./components/Chat";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const initialFormState = {
  hcp_name: "",
  interaction_type: "",
  date: "",
  time: "",
  attendees: "",
  topics: "",
  materials: "",
};

function App() {
  const [formData, setFormData] = useState(initialFormState);
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "Describe the interaction in plain language and I'll fill the log for you.",
    },
  ]);
  const [isLoading, setIsLoading] = useState(false);

  const handleFieldChange = (field, value) => {
    setFormData((current) => ({
      ...current,
      [field]: value,
    }));
  };

  const mergeParsedFields = (parsedFields) => {
    setFormData((current) => ({
      ...current,
      ...parsedFields,
    }));
  };

  const handleSendMessage = async (text) => {
    const trimmedText = text.trim();
    if (!trimmedText) {
      return;
    }

    setMessages((current) => [...current, { role: "user", content: trimmedText }]);
    setIsLoading(true);

    try {
      const response = await axios.post(`${API_BASE_URL}/parse`, {
        text: trimmedText,
      });

      const parsedFields = response.data;
      mergeParsedFields(parsedFields);

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: "Form updated from your message. You can refine anything on the left.",
        },
      ]);
    } catch (error) {
      const message =
        error.response?.data?.detail ||
        "I couldn't parse that message right now. Please try again.";

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: message,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="min-h-screen p-4 md:p-6">
      <div className="mx-auto flex min-h-[calc(100vh-2rem)] max-w-7xl flex-col overflow-hidden rounded-[32px] border border-white/60 bg-white/70 shadow-soft backdrop-blur xl:flex-row">
        <section className="w-full border-b border-ink/10 xl:w-1/2 xl:border-b-0 xl:border-r">
          <Form formData={formData} onFieldChange={handleFieldChange} />
        </section>
        <section className="w-full xl:w-1/2">
          <Chat messages={messages} isLoading={isLoading} onSendMessage={handleSendMessage} />
        </section>
      </div>
    </main>
  );
}

export default App;
