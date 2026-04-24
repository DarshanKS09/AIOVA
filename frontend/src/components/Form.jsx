const interactionOptions = ["Meeting", "Call", "Visit", "Other"];

const fieldClassName =
  "w-full rounded-2xl border border-ink/15 bg-white px-4 py-3 text-sm text-ink outline-none transition focus:border-moss focus:ring-4 focus:ring-moss/10";

function Form({ formData, onFieldChange }) {
  return (
    <div className="flex h-full flex-col p-6 md:p-8">
      <div className="mb-8">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-moss/80">
          Interaction Logger
        </p>
        <h1 className="mt-3 font-display text-4xl text-ink">Structured CRM Entry</h1>
        <p className="mt-3 max-w-xl text-sm leading-6 text-ink/70">
          Review and edit the AI-filled interaction details before saving them into your workflow.
        </p>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <label className="block md:col-span-2">
          <span className="mb-2 block text-sm font-semibold text-ink/80">HCP Name</span>
          <input
            className={fieldClassName}
            type="text"
            value={formData.hcp_name}
            onChange={(event) => onFieldChange("hcp_name", event.target.value)}
            placeholder="Dr Smith"
          />
        </label>

        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-ink/80">Interaction Type</span>
          <select
            className={fieldClassName}
            value={formData.interaction_type}
            onChange={(event) => onFieldChange("interaction_type", event.target.value)}
          >
            <option value="">Select type</option>
            {interactionOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-ink/80">Attendees</span>
          <input
            className={fieldClassName}
            type="text"
            value={formData.attendees}
            onChange={(event) => onFieldChange("attendees", event.target.value)}
            placeholder="Medical liaison, clinic coordinator"
          />
        </label>

        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-ink/80">Date</span>
          <input
            className={fieldClassName}
            type="date"
            value={formData.date}
            onChange={(event) => onFieldChange("date", event.target.value)}
          />
        </label>

        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-ink/80">Time</span>
          <input
            className={fieldClassName}
            type="time"
            value={formData.time}
            onChange={(event) => onFieldChange("time", event.target.value)}
          />
        </label>

        <label className="block md:col-span-2">
          <span className="mb-2 block text-sm font-semibold text-ink/80">Topics</span>
          <textarea
            className={`${fieldClassName} min-h-28 resize-none`}
            value={formData.topics}
            onChange={(event) => onFieldChange("topics", event.target.value)}
            placeholder="Discussed efficacy, patient selection, next steps..."
          />
        </label>

        <label className="block md:col-span-2">
          <span className="mb-2 block text-sm font-semibold text-ink/80">Materials</span>
          <textarea
            className={`${fieldClassName} min-h-28 resize-none`}
            value={formData.materials}
            onChange={(event) => onFieldChange("materials", event.target.value)}
            placeholder="Brochure, leave-behind, clinical summary..."
          />
        </label>
      </div>
    </div>
  );
}

export default Form;
