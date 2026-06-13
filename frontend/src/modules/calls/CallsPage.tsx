import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw, Phone } from "lucide-react";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { callsApi } from "@/services/api";
import type { Call, CallsQueryParams, CallStatus } from "@/types/calls";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { CallsTable, type SortState } from "./CallsTable";
import { CallDetailDrawer } from "./CallDetailDrawer";
import { FilterBar, type FilterValues } from "./FilterBar";

type TabValue = "all" | CallStatus;

const EMPTY_FILTERS: FilterValues = {
  callerName: "",
  phoneNumber: "",
  label: "",
  minDuration: "",
  maxDuration: "",
};

// only a non-negative integer reaches the API; blank, negative or decimal
// is dropped so it can't 422 the backend's ge=0 int param (Number("") is 0,
// so the empty case must be guarded before the integer check)
function toIntParam(value: string): number | undefined {
  const trimmed = value.trim();
  if (trimmed === "") return undefined;
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed) || parsed < 0) return undefined;
  return parsed;
}

const TABS: { label: string; value: TabValue }[] = [
  { label: "All", value: "all" },
  { label: "In Progress", value: "in_progress" },
  { label: "Success", value: "success" },
  { label: "Failed", value: "failed" },
];

const PAGE_SIZE = 20;

export function CallsPage() {
  const [activeTab, setActiveTab] = useState<TabValue>("all");
  const [page, setPage] = useState(1);
  const [selectedCall, setSelectedCall] = useState<Call | null>(null);
  const [filters, setFilters] = useState<FilterValues>(EMPTY_FILTERS);
  const [sort, setSort] = useState<SortState | null>(null);

  const statusFilter = activeTab === "all" ? undefined : activeTab;
  const debouncedCallerName = useDebouncedValue(filters.callerName);
  const debouncedPhoneNumber = useDebouncedValue(filters.phoneNumber);
  const debouncedMinDuration = useDebouncedValue(filters.minDuration);
  const debouncedMaxDuration = useDebouncedValue(filters.maxDuration);

  const minDuration = toIntParam(debouncedMinDuration);
  const maxDuration = toIntParam(debouncedMaxDuration);
  // an inverted range (min>max) would 422; filter by min only instead of
  // issuing a request the backend rejects
  const validMaxDuration =
    minDuration !== undefined && maxDuration !== undefined && minDuration > maxDuration
      ? undefined
      : maxDuration;

  // empty and whitespace-only inputs become undefined: axios drops undefined
  // params, while an empty string would reach the API and 422 on min_length=1
  const queryParams: CallsQueryParams = {
    status: statusFilter,
    page,
    page_size: PAGE_SIZE,
    caller_name: debouncedCallerName.trim() || undefined,
    phone_number: debouncedPhoneNumber.trim() || undefined,
    label: filters.label || undefined,
    min_duration: minDuration,
    max_duration: validMaxDuration,
    sort_by: sort?.by,
    sort_dir: sort?.dir,
  };

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["calls", queryParams],
    queryFn: () => callsApi.list(queryParams),
    refetchInterval: 5000,
  });

  function handleTabChange(tab: TabValue) {
    setActiveTab(tab);
    setPage(1);
  }

  function handleFiltersChange(values: FilterValues) {
    setFilters(values);
    setPage(1);
  }

  function handleSortChange(next: SortState | null) {
    setSort(next);
    setPage(1);
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-white border-b-2 shadow-sm" style={{ borderBottomColor: "#FDDF5C" }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div
                className="w-9 h-9 rounded-xl flex items-center justify-center font-bold text-base shadow"
                style={{ backgroundColor: "#FDDF5C" }}
              >
                <span style={{ color: "#7A6000" }}>V</span>
              </div>
              <span className="font-bold text-xl tracking-tight text-gray-900">VOICO</span>
              <span className="hidden sm:block text-sm text-gray-400 font-normal pl-3 border-l border-gray-200">
                Calls Dashboard
              </span>
            </div>

            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5 text-xs text-gray-500">
                <span
                  className={`inline-block w-2 h-2 rounded-full ${isFetching ? "animate-pulse" : ""}`}
                  style={{ backgroundColor: isFetching ? "#FDDF5C" : "#86efac" }}
                />
                {isFetching ? "Syncing..." : "Live"}
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="text-gray-400 hover:text-gray-700"
                onClick={() => refetch()}
              >
                <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats row */}
        {data && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
            {[
              { label: "Total Calls", value: data.total },
              { label: "In Progress", value: data.counts?.in_progress ?? "—" },
              { label: "Successful", value: data.counts?.success ?? "—" },
              { label: "Failed", value: data.counts?.failed ?? "—" },
            ].map((stat) => (
              <div key={stat.label} className="rounded-xl border border-border bg-white p-4 shadow-sm">
                <p className="text-xs text-muted-foreground mb-1 font-medium">{stat.label}</p>
                <p className="text-2xl font-bold text-foreground">{stat.value}</p>
              </div>
            ))}
          </div>
        )}

        <Card className="bg-white">
          <div className="flex items-center px-6 pt-5 pb-4 border-b border-border">
            <div className="flex gap-1 bg-muted rounded-lg p-1 w-fit">
              {TABS.map((tab) => (
                <button
                  key={tab.value}
                  onClick={() => handleTabChange(tab.value)}
                  className="px-3 py-1.5 rounded-md text-sm font-medium transition-all"
                  style={
                    activeTab === tab.value
                      ? { backgroundColor: "#FDDF5C", color: "#4a3800", boxShadow: "0 1px 3px rgba(0,0,0,0.10)" }
                      : { color: "var(--muted-foreground)" }
                  }
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          <FilterBar values={filters} onChange={handleFiltersChange} />

          <CardContent className="p-0">
            {isError ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mb-3">
                  <Phone className="h-5 w-5 text-red-500" />
                </div>
                <p className="text-sm font-medium text-foreground">Failed to load calls</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Make sure the backend is running at localhost:8000
                </p>
                <Button variant="outline" size="sm" onClick={() => refetch()} className="mt-3">
                  Retry
                </Button>
              </div>
            ) : isLoading ? (
              <div className="flex items-center justify-center py-20">
                <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <CallsTable
                calls={data?.data ?? []}
                onRowClick={setSelectedCall}
                sort={sort}
                onSortChange={handleSortChange}
              />
            )}
          </CardContent>

          {/* Pagination */}
          {data && data.total_pages > 1 && (
            <div
              className="flex items-center justify-between px-6 py-4 border-t border-border"
            >
              <p className="text-sm text-muted-foreground">
                Page {data.page} of {data.total_pages}{" "}
                <span className="opacity-60">({data.total} total)</span>
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                  disabled={page === data.total_pages}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </Card>
      </main>

      <CallDetailDrawer
        key={selectedCall?.id}
        call={selectedCall}
        onClose={() => setSelectedCall(null)}
        onCallUpdated={setSelectedCall}
      />
    </div>
  );
}
