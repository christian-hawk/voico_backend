export type CallStatus = "in_progress" | "success" | "failed";

export type CallLabel =
  | "Sales inquiry"
  | "Support"
  | "Complaint"
  | "Appointment"
  | "Follow-up"
  | "Other";

export type SortField =
  | "phone_number"
  | "caller_name"
  | "status"
  | "label"
  | "duration_seconds"
  | "started_at";

export type SortDir = "asc" | "desc";

export interface Call {
  id: string;
  phone_number: string;
  caller_name: string | null;
  duration_seconds: number | null;
  status: CallStatus;
  summary: string | null;
  label: string | null;
  started_at: string;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
  raw_transcript: string | null;
  notes: string | null;
}

export interface CallCounts {
  in_progress: number;
  success: number;
  failed: number;
}

export interface PaginatedCallsResponse {
  data: Call[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  counts: CallCounts;
}

export interface CallsQueryParams {
  status?: CallStatus;
  page?: number;
  page_size?: number;
  caller_name?: string;
  phone_number?: string;
  label?: CallLabel;
  min_duration?: number;
  max_duration?: number;
  sort_by?: SortField;
  sort_dir?: SortDir;
}
