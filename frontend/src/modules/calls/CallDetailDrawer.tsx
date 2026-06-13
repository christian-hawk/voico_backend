import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import { X, Phone, User, Clock, Calendar, FileText, Sparkles, StickyNote } from "lucide-react";
import { callsApi } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { StatusBadge } from "./CallsTable";
import type { Call } from "@/types/calls";

interface CallDetailDrawerProps {
  call: Call | null;
  onClose: () => void;
}

function DetailRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-3 py-3 border-b border-border last:border-0">
      <div className="mt-0.5 text-muted-foreground">{icon}</div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground mb-0.5">{label}</p>
        <div className="text-sm font-medium text-foreground break-words">{value}</div>
      </div>
    </div>
  );
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return "Not available";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m} min ${s} sec` : `${s} sec`;
}

export function CallDetailDrawer({ call: snapshot, onClose }: CallDetailDrawerProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const queryClient = useQueryClient();

  // keep the open call live: the list polls and the webhook can complete a call
  // while the drawer is open. the clicked row seeds initialData (no loading flash).
  const { data: call } = useQuery({
    queryKey: ["call", snapshot?.id],
    queryFn: () => callsApi.getById(snapshot!.id),
    enabled: snapshot !== null,
    initialData: snapshot ?? undefined,
    refetchInterval: 5000,
  });

  const notesMutation = useMutation({
    mutationFn: (vars: { id: string; notes: string | null }) =>
      callsApi.updateNotes(vars.id, vars.notes),
    onSuccess: (updated) => {
      queryClient.setQueryData(["call", updated.id], updated);
      queryClient.invalidateQueries({ queryKey: ["calls"] });
      setIsEditing(false);
    },
  });

  if (!call) return null;

  const isDirty = isEditing && draft !== (call.notes ?? "");

  // the overlay and the X close the whole drawer; confirm first so an accidental
  // click doesn't silently drop an in-progress edit
  const requestClose = () => {
    if (isDirty && !window.confirm("Discard your unsaved note?")) return;
    onClose();
  };

  const startEditing = () => {
    notesMutation.reset();
    setDraft(call.notes ?? "");
    setIsEditing(true);
  };

  const cancelEditing = () => {
    notesMutation.reset();
    setIsEditing(false);
  };

  const saveNotes = () => {
    const trimmed = draft.trim();
    notesMutation.mutate({ id: call.id, notes: trimmed === "" ? null : trimmed });
  };

  return (
    <>
      <div
        className="fixed inset-0 bg-black/20 z-40 transition-opacity"
        onClick={requestClose}
        aria-hidden="true"
      />

      <aside className="fixed right-0 top-0 h-full w-full max-w-md bg-white shadow-2xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div>
            <h2 className="text-base font-semibold text-foreground">Call Details</h2>
            <p className="text-xs text-muted-foreground font-mono mt-0.5">#{call.id.slice(0, 8)}</p>
          </div>
          <button
            onClick={requestClose}
            className="rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Status banner */}
        <div className="px-6 py-3 bg-muted/50 border-b border-border flex items-center justify-between">
          <StatusBadge status={call.status} />
          {call.label && (
            <span className="inline-flex items-center rounded-md px-2 py-1 text-xs font-medium border border-border bg-white text-foreground">
              {call.label}
            </span>
          )}
        </div>

        {/* Scrollable body: details, summary, transcript and notes scroll together,
            so a long note can't collapse the details or push the footer out of reach */}
        <div className="flex-1 overflow-y-auto">
          <div className="px-6 py-4">
            <DetailRow
              icon={<Phone className="h-4 w-4" />}
              label="Phone Number"
              value={<span className="font-mono">{call.phone_number}</span>}
            />
            <DetailRow
              icon={<User className="h-4 w-4" />}
              label="Caller Name"
              value={call.caller_name ?? "Unknown"}
            />
            <DetailRow
              icon={<Clock className="h-4 w-4" />}
              label="Duration"
              value={formatDuration(call.duration_seconds)}
            />
            <DetailRow
              icon={<Calendar className="h-4 w-4" />}
              label="Started At"
              value={format(new Date(call.started_at), "PPpp")}
            />
            {call.ended_at && (
              <DetailRow
                icon={<Calendar className="h-4 w-4" />}
                label="Ended At"
                value={format(new Date(call.ended_at), "PPpp")}
              />
            )}
          </div>

          {/* AI Summary */}
          {call.summary && (
            <div className="px-6 py-4 border-t border-border">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="h-4 w-4" style={{ color: "#FDDF5C" }} />
                <h3 className="text-sm font-semibold text-foreground">AI Summary</h3>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">{call.summary}</p>
            </div>
          )}

          {/* Transcript */}
          {call.raw_transcript && (
            <div className="px-6 py-4 border-t border-border">
              <div className="flex items-center gap-2 mb-2">
                <FileText className="h-4 w-4 text-muted-foreground" />
                <h3 className="text-sm font-semibold text-foreground">Transcript</h3>
              </div>
              <div className="bg-muted rounded-lg p-3 max-h-48 overflow-y-auto">
                <pre className="text-xs text-muted-foreground whitespace-pre-wrap font-mono leading-relaxed">
                  {call.raw_transcript}
                </pre>
              </div>
            </div>
          )}

          {/* Notes */}
          <div className="px-6 py-4 border-t border-border">
            <div className="flex items-center justify-between gap-2 mb-2">
              <div className="flex items-center gap-2">
                <StickyNote className="h-4 w-4 text-muted-foreground" />
                <h3 className="text-sm font-semibold text-foreground">Notes</h3>
              </div>
              {!isEditing && call.notes && (
                <Button variant="ghost" size="sm" onClick={startEditing}>
                  Edit
                </Button>
              )}
            </div>
            {isEditing ? (
              <div className="space-y-2">
                <Textarea
                  autoFocus
                  value={draft}
                  placeholder="Add notes…"
                  disabled={notesMutation.isPending}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Escape" && !notesMutation.isPending) cancelEditing();
                  }}
                />
                {notesMutation.isError && (
                  <p className="text-xs text-red-500">Failed to save notes. Try again.</p>
                )}
                <div className="flex items-center gap-2">
                  <Button size="sm" onClick={saveNotes} disabled={notesMutation.isPending}>
                    Save
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={cancelEditing}
                    disabled={notesMutation.isPending}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ) : call.notes ? (
              <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
                {call.notes}
              </p>
            ) : (
              <button
                type="button"
                onClick={startEditing}
                className="text-sm text-muted-foreground italic hover:text-foreground transition-colors"
              >
                Add notes…
              </button>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-border bg-muted/30">
          <p className="text-xs text-muted-foreground">
            Created {format(new Date(call.created_at), "PPpp")}
          </p>
        </div>
      </aside>
    </>
  );
}
