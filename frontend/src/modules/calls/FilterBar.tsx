import { X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { CallLabel } from "@/types/calls";

const LABELS: CallLabel[] = [
  "Sales inquiry",
  "Support",
  "Complaint",
  "Appointment",
  "Follow-up",
  "Other",
];

export interface FilterValues {
  callerName: string;
  phoneNumber: string;
  label: CallLabel | "";
  minDuration: string;
  maxDuration: string;
}

interface FilterBarProps {
  values: FilterValues;
  onChange: (values: FilterValues) => void;
}

export function FilterBar({ values, onChange }: FilterBarProps) {
  const set = (patch: Partial<FilterValues>) => onChange({ ...values, ...patch });

  const chips: { key: keyof FilterValues; text: string }[] = [];
  if (values.callerName.trim()) chips.push({ key: "callerName", text: `Caller: ${values.callerName.trim()}` });
  if (values.phoneNumber.trim()) chips.push({ key: "phoneNumber", text: `Phone: ${values.phoneNumber.trim()}` });
  if (values.label) chips.push({ key: "label", text: `Label: ${values.label}` });
  if (values.minDuration !== "") chips.push({ key: "minDuration", text: `Min: ${values.minDuration}s` });
  if (values.maxDuration !== "") chips.push({ key: "maxDuration", text: `Max: ${values.maxDuration}s` });

  return (
    <div className="px-6 py-4 border-b border-border space-y-3">
      <div className="flex flex-wrap gap-2">
        <Input
          value={values.callerName}
          onChange={(e) => set({ callerName: e.target.value })}
          placeholder="Caller name…"
          className="w-44"
        />
        <Input
          value={values.phoneNumber}
          onChange={(e) => set({ phoneNumber: e.target.value })}
          placeholder="Phone…"
          className="w-40"
        />
        <Select
          value={values.label}
          onChange={(e) => set({ label: e.target.value as CallLabel | "" })}
          className="w-40"
        >
          <option value="">All labels</option>
          {LABELS.map((label) => (
            <option key={label} value={label}>
              {label}
            </option>
          ))}
        </Select>
        <Input
          type="number"
          min={0}
          value={values.minDuration}
          onChange={(e) => set({ minDuration: e.target.value })}
          placeholder="Min (s)"
          className="w-24"
        />
        <Input
          type="number"
          min={0}
          value={values.maxDuration}
          onChange={(e) => set({ maxDuration: e.target.value })}
          placeholder="Max (s)"
          className="w-24"
        />
      </div>

      {chips.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {chips.map((chip) => (
            <span
              key={chip.key}
              className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-foreground"
            >
              {chip.text}
              <button
                type="button"
                onClick={() => set({ [chip.key]: "" })}
                className="text-muted-foreground hover:text-foreground transition-colors"
                aria-label={`Remove ${chip.text}`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
