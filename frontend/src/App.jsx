import { useEffect, useState } from "react";
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
  const [editingEntryId, setEditingEntryId] = useState(null);
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

  useEffect(() => {
    const loadEntries = async () => {
      try {
        const response = await axios.post(`${API_BASE_URL}/agent/invoke`, {
          action: "list_entries",
        });
        setEntries(response.data.entries || []);
      } catch {
        pushAssistantMessage("I couldn't load saved interactions from the database.");
      }
    };

    loadEntries();
  }, []);

  const handleFieldChange = (field, value) => {
    setFormData((current) => ({
      ...current,
      [field]: value,
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
      const response = await axios.post(`${API_BASE_URL}/agent/invoke`, {
        action: "process_message",
        user_input: trimmedText,
        current_state: formData,
      });

      if (response.data.form_data) {
        setFormData((current) => ({
          ...current,
          ...response.data.form_data,
        }));
      }

      pushAssistantMessage(
        response.data.message || "Form updated from your message. You can keep refining anything on the left.",
      );
    } catch (error) {
      pushAssistantMessage(
        error.response?.data?.detail || "I couldn't process that message right now. Please try again.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const applyAgentSaveResponse = (responseData) => {
    if (responseData.entries) {
      setEntries(responseData.entries);
    }
    if (responseData.entry) {
      setFormData((current) => ({
        ...current,
        ...responseData.entry,
      }));
    }
    if (responseData.message) {
      pushAssistantMessage(responseData.message);
    }
  };

  const handleSaveEntry = async () => {
    setIsSaving(true);

    try {
      if (editingEntryId) {
        const response = await axios.post(`${API_BASE_URL}/agent/invoke`, {
          action: "update_entry",
          entry_id: editingEntryId,
          form_data: formData,
        });
        applyAgentSaveResponse(response.data);
        setEditingEntryId(null);
        return;
      }

      const response = await axios.post(`${API_BASE_URL}/agent/invoke`, {
        action: "save_entry",
        form_data: formData,
      });

      if (response.data.status === "duplicate_detected") {
        setDuplicateState({
          ...response.data.duplicate,
          newEntry: formData,
        });
        pushAssistantMessage(
          response.data.message || "Duplicate detected. Choose Merge or Save as New.",
        );
        return;
      }

      applyAgentSaveResponse(response.data);
    } catch (error) {
      pushAssistantMessage(
        error.response?.data?.detail || "I couldn't save the interaction right now.",
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleMergeDuplicate = async () => {
    if (!duplicateState?.matched_record?.id) {
      return;
    }

    setIsSaving(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/agent/invoke`, {
        action: "merge_entry",
        matched_entry_id: duplicateState.matched_record.id,
        form_data: duplicateState.newEntry,
      });
      setDuplicateState(null);
      applyAgentSaveResponse(response.data);
    } catch (error) {
      pushAssistantMessage(
        error.response?.data?.detail || "I couldn't merge the duplicate interaction right now.",
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveAsNew = async () => {
    if (!duplicateState) {
      return;
    }

    setIsSaving(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/agent/invoke`, {
        action: "save_new_entry",
        form_data: duplicateState.newEntry,
      });
      setDuplicateState(null);
      applyAgentSaveResponse(response.data);
    } catch (error) {
      pushAssistantMessage(
        error.response?.data?.detail || "I couldn't save the interaction as a new record right now.",
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancelDuplicate = () => {
    setDuplicateState(null);
    pushAssistantMessage("Duplicate save cancelled. You can keep editing before saving.");
  };

  const handleEditEntry = async (entryId) => {
    setIsLoading(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/agent/invoke`, {
        action: "load_entry",
        entry_id: entryId,
      });
      if (response.data.form_data) {
        setFormData((current) => ({
          ...current,
          ...response.data.form_data,
        }));
      }
      setEditingEntryId(entryId);
      pushAssistantMessage(
        response.data.message || "Saved interaction loaded into the form for editing.",
      );
    } catch (error) {
      pushAssistantMessage(
        error.response?.data?.detail || "I couldn't load that saved interaction right now.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteEntry = async (entryId) => {
    setIsSaving(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/agent/invoke`, {
        action: "delete_entry",
        entry_id: entryId,
      });
      if (editingEntryId === entryId) {
        setEditingEntryId(null);
        setFormData(initialFormState);
      }
      applyAgentSaveResponse(response.data);
    } catch (error) {
      pushAssistantMessage(
        error.response?.data?.detail || "I couldn't delete that saved interaction right now.",
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleResetForm = () => {
    setFormData(initialFormState);
    setEditingEntryId(null);
    pushAssistantMessage("The form is ready for a new interaction.");
  };

  return (
    <main className="min-h-screen bg-[#f3f4f6] px-4 py-5 md:px-6">
      <div className="mx-auto flex min-h-[calc(100vh-2.5rem)] max-w-[1400px] flex-col gap-5 xl:flex-row">
        <section className="min-h-[720px] w-full overflow-hidden rounded-[18px] border border-slate-200 bg-white shadow-[0_10px_30px_rgba(15,23,42,0.08)] xl:w-[66%]">
          <Form
            formData={formData}
            onFieldChange={handleFieldChange}
            onSaveEntry={handleSaveEntry}
            onEditEntry={handleEditEntry}
            onDeleteEntry={handleDeleteEntry}
            onResetForm={handleResetForm}
            entries={entries}
            editingEntryId={editingEntryId}
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
              Duplicate detected
            </div>
            <h2 className="mt-4 text-xl font-semibold text-slate-800">
              Duplicate interaction detected ({duplicateState.confidence}% match)
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">{duplicateState.reason}</p>
            <p className="mt-3 text-sm leading-6 text-slate-500">
              Do you want to merge this interaction with the saved record, save it as a new record,
              or cancel?
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
                onClick={handleSaveAsNew}
                className="inline-flex flex-1 items-center justify-center rounded-[12px] border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
                disabled={isSaving}
              >
                Save New
              </button>
              <button
                type="button"
                onClick={handleCancelDuplicate}
                className="inline-flex flex-1 items-center justify-center rounded-[12px] border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
                disabled={isSaving}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}

export default App;
