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
  const [entries, setEntries] = useState([]);
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "Describe the interaction in plain language and I'll fill the log for you.",
    },
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [duplicateState, setDuplicateState] = useState(null);

  const pushAssistantMessage = (content) => {
    setMessages((current) => [...current, { role: "assistant", content }]);
  };

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
        current_state: formData,
      });

      const parsedFields = response.data;
      mergeParsedFields(parsedFields);
      const hasUpdates = Object.keys(parsedFields).length > 0;

      pushAssistantMessage(
        hasUpdates
          ? "Form updated from your message. You can keep refining anything on the left."
          : "I understood the message, but it did not change any form fields.",
      );
    } catch (error) {
      pushAssistantMessage(
        error.response?.data?.detail || "I couldn't parse that message right now. Please try again.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const saveAsNewEntry = (entry) => {
    const savedEntry = {
      id: Date.now(),
      ...entry,
    };
    setEntries((current) => [savedEntry, ...current]);
    setDuplicateState(null);
    pushAssistantMessage("Interaction saved as a new entry.");
  };

  const handleSaveEntry = async () => {
    setIsSaving(true);

    try {
      const response = await axios.post(`${API_BASE_URL}/check-duplicate`, {
        new_entry: formData,
        existing_entries: entries.map(({ id, ...entry }) => entry),
      });

      const result = response.data;
      if (result.is_duplicate && result.matched_index !== null) {
        setDuplicateState({
          ...result,
          newEntry: formData,
        });
        pushAssistantMessage(
          `Similar interaction found (${result.confidence}% match). Choose Merge or Create New.`,
        );
        return;
      }

      saveAsNewEntry(formData);
    } catch (error) {
      pushAssistantMessage(
        error.response?.data?.detail || "I couldn't check for duplicates right now. Please try again.",
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleMergeDuplicate = async () => {
    if (!duplicateState || duplicateState.matched_index === null) {
      return;
    }

    setIsSaving(true);

    try {
      const matchedEntry = entries[duplicateState.matched_index];
      const { id, ...existingPayload } = matchedEntry;
      const response = await axios.post(`${API_BASE_URL}/merge-entry`, {
        existing: existingPayload,
        new: duplicateState.newEntry,
      });

      const mergedEntry = response.data;
      setEntries((current) =>
        current.map((entry, index) =>
          index === duplicateState.matched_index ? { ...entry, ...mergedEntry } : entry,
        ),
      );
      setFormData((current) => ({
        ...current,
        ...mergedEntry,
      }));
      setDuplicateState(null);
      pushAssistantMessage("The duplicate interaction was merged successfully.");
    } catch (error) {
      pushAssistantMessage(
        error.response?.data?.detail || "I couldn't merge the duplicate entry right now.",
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleKeepSeparate = () => {
    if (!duplicateState) {
      return;
    }

    saveAsNewEntry(duplicateState.newEntry);
  };

  return (
    <main className="min-h-screen bg-[#f3f4f6] px-4 py-5 md:px-6">
      <div className="mx-auto flex min-h-[calc(100vh-2.5rem)] max-w-[1400px] flex-col gap-5 xl:flex-row">
        <section className="min-h-[720px] w-full overflow-hidden rounded-[18px] border border-slate-200 bg-white shadow-[0_10px_30px_rgba(15,23,42,0.08)] xl:w-[66%]">
          <Form
            formData={formData}
            onFieldChange={handleFieldChange}
            onSaveEntry={handleSaveEntry}
            entries={entries}
            isSaving={isSaving}
          />
        </section>
        <section className="min-h-[720px] w-full overflow-hidden rounded-[18px] border border-slate-200 bg-white shadow-[0_10px_30px_rgba(15,23,42,0.08)] xl:w-[34%]">
          <Chat messages={messages} isLoading={isLoading} onSendMessage={handleSendMessage} />
        </section>
      </div>

      {duplicateState ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/30 px-4">
          <div className="w-full max-w-md rounded-[18px] border border-amber-200 bg-white p-6 shadow-[0_20px_60px_rgba(15,23,42,0.18)]">
            <div className="inline-flex items-center rounded-full bg-amber-100 px-3 py-1 text-sm font-semibold text-amber-800">
              Potential Duplicate
            </div>
            <h2 className="mt-4 text-xl font-semibold text-slate-800">
              Similar interaction found ({duplicateState.confidence}% match)
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">{duplicateState.reason}</p>
            <p className="mt-3 text-sm leading-6 text-slate-500">
              Do you want to merge this interaction with the existing entry, or keep it as a new
              record?
            </p>

            <div className="mt-6 flex gap-3">
              <button
                type="button"
                onClick={handleMergeDuplicate}
                className="inline-flex flex-1 items-center justify-center rounded-[12px] bg-blue-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-60"
                disabled={isSaving}
              >
                Merge
              </button>
              <button
                type="button"
                onClick={handleKeepSeparate}
                className="inline-flex flex-1 items-center justify-center rounded-[12px] border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
                disabled={isSaving}
              >
                Create New
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}

export default App;
