import { supabase } from "@/integrations/supabase/client";

/**
 * VPT Scanner API Service
 * Uses Supabase directly so the scanner UI works inside BARN without
 * requiring the separate Flask backend.
 */

// Types
export interface VPTProperty {
  pdf_file: string;
  bill_url: string;
  apn: string;
  parcel_number: string;
  tracer_number: string;
  location_of_property: string;
  tax_year: string;
  last_payment: string;
  delinquent: string;
  power_status: string;
  has_vpt: string;
  vpt_marker: string;
  city: string;
  is_favorite: boolean;
  mailing_address: string;
  situs_address: string;
  situs_city: string;
  situs_zip: string;
  pdf_url: string;
  maps_url: string;
  condition_score: number | null;
  condition_notes: string;
  streetview_image_path: string;
  streetview_url: string;
  property_search_url: string;
  mailing_search_url: string;
  research_status: string;
  lat: number;
  lng: number;
}

export interface VPTMarker {
  lat: number;
  lng: number;
  apn: string;
  parcel_number: string;
  tracer_number: string;
  location: string;
  tax_year: string;
  last_payment: string;
  delinquent: string;
  power_status: string;
  has_vpt: string;
  vpt_marker: string;
  city: string;
  is_favorite: boolean;
  mailing_address: string;
  situs_address: string;
  bill_url: string;
  maps_url: string;
  streetview_url: string;
  condition_score: number | null;
  property_search_url: string;
  mailing_search_url: string;
}

export interface VPTFilters {
  q?: string;
  zip?: string;
  city?: string;
  power?: string;
  vpt?: string;
  delinquent?: string;
  fav?: string;
  condition?: string;
  outofstate?: string;
  research?: string;
  sort?: string;
  order?: string;
  page?: number;
  page_size?: number;
}

export interface VPTPropertiesResponse {
  rows: VPTProperty[];
  total: number;
  total_pages: number;
  page: number;
  page_size: number;
}

export interface VPTScanStatus {
  is_running: boolean;
  continuous_mode: boolean;
  current_city: string | null;
  available_cities: string[];
  cities_completed: string[];
  total_bills: number;
  vpt_count: number;
  city_counts: Record<string, number>;
}

export interface VPTResearchStatus {
  is_running: boolean;
  api_configured: boolean;
  current_apn: string | null;
  queue_length: number;
  completed: number;
  total_completed: number;
  total_pending: number;
  total_failed: number;
}

export interface VPTConditionStatus {
  is_running: boolean;
  api_configured: boolean;
  current_apn: string | null;
  total_scanned: number;
  average_score: number | null;
  poor_condition: number;
}

export interface VPTPgeStatus {
  is_running: boolean;
  current_address: string | null;
  total_power_on: number;
  total_power_off: number;
  total_unchecked: number;
}

type RpcBillRow = {
  apn: string;
  pdf_file: string | null;
  bill_url: string | null;
  parcel_number: string | null;
  tracer_number: string | null;
  location_of_property: string | null;
  tax_year: string | null;
  last_payment: string | null;
  delinquent: number | null;
  power_status: string | null;
  has_vpt: number | null;
  vpt_marker: string | null;
  city: string | null;
  condition_score: number | null;
  condition_notes: string | null;
  streetview_image_path: string | null;
  property_search_url: string | null;
  mailing_search_url: string | null;
  research_status: string | null;
  row_json: string | null;
  situs_zip: string | null;
};

const DEFAULT_PAGE_SIZE = 25;

const parseRowJson = (value: unknown): Record<string, unknown> => {
  if (!value) return {};
  if (typeof value === "object") return value as Record<string, unknown>;
  if (typeof value !== "string") return {};

  try {
    return JSON.parse(value) as Record<string, unknown>;
  } catch {
    return {};
  }
};

const toString = (value: unknown): string => {
  if (value === null || value === undefined) return "";
  return String(value);
};

const toYesNo = (value: number | null | undefined): string => (value === 1 ? "Yes" : "No");

const toFlag = (value?: string): number => (value === "1" ? 1 : 0);

const normalizePowerFilter = (value?: string): string => {
  if (!value || value === "all") return "";
  return value;
};

const normalizeOrder = (value?: string): string => (value?.toLowerCase() === "desc" ? "desc" : "asc");

const normalizeSort = (value?: string): string => value || "location_of_property";

const webMercatorToLatLng = (x: number, y: number): { lat: number; lng: number } => {
  const lng = (x / 20037508.34) * 180;
  let lat = (y / 20037508.34) * 180;
  lat = (180 / Math.PI) * (2 * Math.atan(Math.exp((lat * Math.PI) / 180)) - Math.PI / 2);
  return { lat, lng };
};

const extractCoordinates = (rowJson: Record<string, unknown>): { lat: number; lng: number } => {
  const rawX = Number(rowJson.CENTROID_X ?? rowJson.X_CORD ?? rowJson.x ?? 0);
  const rawY = Number(rowJson.CENTROID_Y ?? rowJson.Y_CORD ?? rowJson.y ?? 0);
  if (!Number.isFinite(rawX) || !Number.isFinite(rawY) || rawX === 0 || rawY === 0) {
    return { lat: 0, lng: 0 };
  }
  return webMercatorToLatLng(rawX, rawY);
};

const buildMapsUrl = (location: string): string => {
  if (!location) return "";
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(location)}`;
};

const buildStreetviewPageUrl = (lat: number, lng: number, location: string): string => {
  if (lat && lng) {
    return `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lng}`;
  }
  if (location) {
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(location)}`;
  }
  return "";
};

const buildStreetviewImageUrl = (lat: number, lng: number, location: string): string => {
  if (lat && lng) {
    return `https://maps.googleapis.com/maps/api/streetview?size=1280x720&location=${lat},${lng}`;
  }
  if (location) {
    return `https://maps.googleapis.com/maps/api/streetview?size=1280x720&location=${encodeURIComponent(location)}`;
  }
  return "";
};

const normalizeRow = (row: RpcBillRow, favoritesSet: Set<string>): VPTProperty => {
  const parcel = parseRowJson(row.row_json);
  const { lat, lng } = extractCoordinates(parcel);
  const location = toString(row.location_of_property);
  const city = toString(row.city || parcel.SitusCity);
  const situsAddress = toString(parcel.SitusAddress);
  const mailingAddress = toString(parcel.MailingAddress);

  return {
    pdf_file: toString(row.pdf_file),
    bill_url: toString(row.bill_url),
    apn: toString(row.apn),
    parcel_number: toString(row.parcel_number),
    tracer_number: toString(row.tracer_number),
    location_of_property: location,
    tax_year: toString(row.tax_year),
    last_payment: toString(row.last_payment),
    delinquent: toYesNo(row.delinquent),
    power_status: toString(row.power_status).toUpperCase(),
    has_vpt: toYesNo(row.has_vpt),
    vpt_marker: toString(row.vpt_marker),
    city,
    is_favorite: favoritesSet.has(row.apn),
    mailing_address: mailingAddress,
    situs_address: situsAddress,
    situs_city: toString(parcel.SitusCity),
    situs_zip: toString(row.situs_zip || parcel.SitusZip),
    pdf_url: "",
    maps_url: buildMapsUrl(location),
    condition_score: row.condition_score,
    condition_notes: toString(row.condition_notes),
    streetview_image_path: toString(row.streetview_image_path),
    streetview_url: buildStreetviewPageUrl(lat, lng, location),
    property_search_url: toString(row.property_search_url),
    mailing_search_url: toString(row.mailing_search_url),
    research_status: toString(row.research_status || "unchecked"),
    lat,
    lng,
  };
};

const toMarker = (property: VPTProperty): VPTMarker => ({
  lat: property.lat,
  lng: property.lng,
  apn: property.apn,
  parcel_number: property.parcel_number,
  tracer_number: property.tracer_number,
  location: property.location_of_property,
  tax_year: property.tax_year,
  last_payment: property.last_payment,
  delinquent: property.delinquent,
  power_status: property.power_status,
  has_vpt: property.has_vpt,
  vpt_marker: property.vpt_marker,
  city: property.city,
  is_favorite: property.is_favorite,
  mailing_address: property.mailing_address,
  situs_address: property.situs_address,
  bill_url: property.bill_url,
  maps_url: property.maps_url,
  streetview_url: property.streetview_url,
  condition_score: property.condition_score,
  property_search_url: property.property_search_url,
  mailing_search_url: property.mailing_search_url,
});

const fetchFavoritesSet = async (): Promise<Set<string>> => {
  const { data, error } = await supabase.from("favorites").select("apn");
  if (error) {
    throw new Error(error.message);
  }
  return new Set((data || []).map((row) => row.apn));
};

const buildRpcArgs = (filters: VPTFilters, limit: number, offset: number) => ({
  p_q: filters.q || "",
  p_zip: filters.zip || "",
  p_power: normalizePowerFilter(filters.power),
  p_fav: toFlag(filters.fav),
  p_city: (filters.city || "").toUpperCase(),
  p_vpt: toFlag(filters.vpt),
  p_delinquent: toFlag(filters.delinquent),
  p_condition: filters.condition || "",
  p_outofstate: toFlag(filters.outofstate),
  p_sort: normalizeSort(filters.sort),
  p_order: normalizeOrder(filters.order),
  p_limit: limit,
  p_offset: offset,
  p_research: filters.research || "",
});

const buildLegacyRpcArgs = (filters: VPTFilters, limit: number, offset: number) => ({
  p_q: filters.q || "",
  p_zip: filters.zip || "",
  p_power: normalizePowerFilter(filters.power),
  p_fav: toFlag(filters.fav),
  p_city: (filters.city || "").toUpperCase(),
  p_vpt: toFlag(filters.vpt),
  p_delinquent: toFlag(filters.delinquent),
  p_condition: filters.condition || "",
  p_outofstate: toFlag(filters.outofstate),
  p_sort: normalizeSort(filters.sort),
  p_order: normalizeOrder(filters.order),
  p_limit: limit,
  p_offset: offset,
});

const isMissingResearchOverload = (message: string | undefined): boolean => {
  if (!message) return false;
  return (
    message.includes("Could not find the function public.get_bills_filtered") ||
    message.includes("function get_bills_filtered")
  );
};

const parseFilteredPayload = (payload: unknown): { rows: RpcBillRow[]; total: number } => {
  if (!payload || typeof payload !== "object") {
    return { rows: [], total: 0 };
  }

  const record = payload as { rows?: unknown; total?: unknown };
  const rows = Array.isArray(record.rows) ? (record.rows as RpcBillRow[]) : [];
  const total = typeof record.total === "number" ? record.total : rows.length;

  return { rows, total };
};

type WorkerRoute = {
  method: "GET" | "POST";
  path: string;
};

type WorkerActionResult = {
  status: string;
  message: string;
};

type WorkerEnvelope<T> = {
  ok?: boolean;
  status?: number;
  data?: T;
  error?: string;
  message?: string;
};

const workerRoutes: Record<string, WorkerRoute> = {
  "scan.status": { method: "GET", path: "/api/scan/status" },
  "scan.start": { method: "POST", path: "/api/scan/start" },
  "scan.stop": { method: "POST", path: "/api/scan/stop" },
  "research.status": { method: "GET", path: "/api/research/status" },
  "research.start": { method: "POST", path: "/api/research/start" },
  "research.start_all": { method: "POST", path: "/api/research/start-all" },
  "condition.status": { method: "GET", path: "/api/condition/status" },
  "condition.start": { method: "POST", path: "/api/condition/start" },
  "condition.start_all": { method: "POST", path: "/api/condition/start-all" },
  "pge.status": { method: "GET", path: "/api/pge/status" },
  "pge.start": { method: "POST", path: "/api/pge/start" },
  "pge.start_all": { method: "POST", path: "/api/pge/start-all" },
  "pge.stop": { method: "POST", path: "/api/pge/stop" },
};

const browserWorkerBaseUrl = (
  (import.meta.env.VITE_VPT_WORKER_BASE_URL as string | undefined) || ""
)
  .trim()
  .replace(/\/+$/, "");

const browserWorkerApiKey = (
  (import.meta.env.VITE_VPT_WORKER_API_KEY as string | undefined) || ""
).trim();

const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" ? (value as Record<string, unknown>) : {};

const asNumber = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

const asBoolean = (value: unknown): boolean | null =>
  typeof value === "boolean" ? value : null;

const asString = (value: unknown): string | null =>
  typeof value === "string" && value.trim() ? value : null;

const asStringArray = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && item.trim()) : [];

const toWorkerErrorMessage = (value: unknown): string => {
  const record = asRecord(value);
  return (
    asString(record.error) ||
    asString(record.message) ||
    "Scanner worker request failed."
  );
};

const toActionResult = (value: unknown, fallbackMessage: string): WorkerActionResult => {
  const record = asRecord(value);
  return {
    status: asString(record.status) || "ok",
    message: asString(record.message) || fallbackMessage,
  };
};

const invokeWorkerDirect = async <T>(
  action: string,
  payload: Record<string, unknown> | undefined,
  optional: boolean
): Promise<T | null> => {
  if (!browserWorkerBaseUrl) {
    if (optional) return null;
    throw new Error(
      "Scanner worker is not configured. Set VPT_WORKER_BASE_URL (server) or VITE_VPT_WORKER_BASE_URL (browser)."
    );
  }

  const route = workerRoutes[action];
  if (!route) {
    if (optional) return null;
    throw new Error(`Unsupported scanner action: ${action}`);
  }

  const headers: HeadersInit = {
    Accept: "application/json",
  };

  if (route.method === "POST") {
    headers["Content-Type"] = "application/json";
  }

  if (browserWorkerApiKey) {
    headers["X-API-Key"] = browserWorkerApiKey;
  }

  try {
    const response = await fetch(`${browserWorkerBaseUrl}${route.path}`, {
      method: route.method,
      headers,
      body: route.method === "POST" ? JSON.stringify(payload || {}) : undefined,
    });

    const raw = await response.text();
    let data: unknown = null;

    if (raw) {
      try {
        data = JSON.parse(raw);
      } catch {
        data = { raw };
      }
    }

    if (!response.ok) {
      if (optional) return null;
      throw new Error(toWorkerErrorMessage(data));
    }

    return (data as T) || null;
  } catch (error) {
    if (optional) return null;
    throw error instanceof Error ? error : new Error("Unable to reach scanner worker.");
  }
};

const invokeWorker = async <T>(
  action: string,
  payload?: Record<string, unknown>,
  optional = false
): Promise<T | null> => {
  const { data, error } = await supabase.functions.invoke<WorkerEnvelope<T>>(
    "vpt-scanner-control",
    { body: { action, payload } }
  );

  if (error || !data?.ok) {
    const edgeError = error?.message || toWorkerErrorMessage(data);

    if (browserWorkerBaseUrl) {
      return invokeWorkerDirect<T>(action, payload, optional);
    }

    if (optional) return null;
    throw new Error(edgeError);
  }

  return (data.data as T) || null;
};

// Authentication compatibility for older UI paths.
export async function vptLogin(_username: string, _password: string): Promise<boolean> {
  return true;
}

export async function vptLogout(): Promise<void> {
  return;
}

export async function vptCheckSession(): Promise<boolean> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return Boolean(session);
}

// Properties
export async function vptGetProperties(filters: VPTFilters = {}): Promise<VPTPropertiesResponse> {
  const pageSize = Math.max(10, Math.min(filters.page_size ?? DEFAULT_PAGE_SIZE, 200));
  const page = Math.max(1, filters.page ?? 1);
  const offset = (page - 1) * pageSize;

  const [favoritesSet, rpcResult] = await Promise.all([
    fetchFavoritesSet(),
    supabase.rpc("get_bills_filtered", buildRpcArgs(filters, pageSize, offset)),
  ]);

  let finalResult = rpcResult;
  if (rpcResult.error && isMissingResearchOverload(rpcResult.error.message)) {
    finalResult = await supabase.rpc(
      "get_bills_filtered",
      buildLegacyRpcArgs(filters, pageSize, offset)
    );
  }

  if (finalResult.error) {
    throw new Error(finalResult.error.message);
  }

  const { rows, total } = parseFilteredPayload(finalResult.data);
  const normalizedRows = rows.map((row) => normalizeRow(row, favoritesSet));

  return {
    rows: normalizedRows,
    total,
    total_pages: Math.max(1, Math.ceil(total / pageSize)),
    page,
    page_size: pageSize,
  };
}

export async function vptGetMarkers(filters: VPTFilters = {}): Promise<VPTMarker[]> {
  const rpcArgs = {
    p_q: filters.q || "",
    p_zip: filters.zip || "",
    p_power: normalizePowerFilter(filters.power),
    p_fav: toFlag(filters.fav),
    p_city: (filters.city || "").toUpperCase(),
    p_vpt: toFlag(filters.vpt),
    p_delinquent: toFlag(filters.delinquent),
  };

  const [favoritesSet, rpcResult] = await Promise.all([
    fetchFavoritesSet(),
    supabase.rpc("get_bills_for_map", rpcArgs),
  ]);

  if (rpcResult.error) {
    throw new Error(rpcResult.error.message);
  }

  const rows = Array.isArray(rpcResult.data) ? (rpcResult.data as RpcBillRow[]) : [];
  return rows.map((row) => toMarker(normalizeRow(row, favoritesSet)));
}

// Favorites
export async function vptGetFavorites(): Promise<string[]> {
  const { data, error } = await supabase.from("favorites").select("apn");
  if (error) {
    throw new Error(error.message);
  }
  return (data || []).map((row) => row.apn);
}

export async function vptToggleFavorite(
  apn: string
): Promise<{ status: string; apn: string; favorited: boolean }> {
  const { data: existing, error: existingError } = await supabase
    .from("favorites")
    .select("apn")
    .eq("apn", apn)
    .maybeSingle();

  if (existingError) {
    throw new Error(existingError.message);
  }

  if (existing) {
    const { error } = await supabase.from("favorites").delete().eq("apn", apn);
    if (error) {
      throw new Error(error.message);
    }
    return { status: "ok", apn, favorited: false };
  }

  const { error } = await supabase.from("favorites").insert({ apn });
  if (error) {
    throw new Error(error.message);
  }
  return { status: "ok", apn, favorited: true };
}

// Scan Control
export async function vptGetScanStatus(): Promise<VPTScanStatus> {
  const [totalResult, vptResult, cityRowsResult] = await Promise.all([
    supabase.from("bills").select("apn", { count: "exact", head: true }),
    supabase.from("bills").select("apn", { count: "exact", head: true }).eq("has_vpt", 1),
    supabase.from("bills").select("city").not("city", "is", null),
  ]);

  if (totalResult.error) throw new Error(totalResult.error.message);
  if (vptResult.error) throw new Error(vptResult.error.message);
  if (cityRowsResult.error) throw new Error(cityRowsResult.error.message);

  const cityCounts: Record<string, number> = {};
  for (const row of cityRowsResult.data || []) {
    const city = row.city || "UNKNOWN";
    cityCounts[city] = (cityCounts[city] || 0) + 1;
  }

  const availableCities = Object.keys(cityCounts).sort((a, b) => a.localeCompare(b));
  const workerStatus = asRecord(
    await invokeWorker<Record<string, unknown>>("scan.status", undefined, true)
  );
  const workerAvailableCities = asStringArray(workerStatus.available_cities);
  const workerCompletedCities = asStringArray(workerStatus.cities_completed);

  return {
    is_running: asBoolean(workerStatus.is_running) ?? false,
    continuous_mode: asBoolean(workerStatus.continuous_mode) ?? false,
    current_city: asString(workerStatus.current_city),
    available_cities: workerAvailableCities.length ? workerAvailableCities : availableCities,
    cities_completed: workerCompletedCities.length ? workerCompletedCities : availableCities,
    total_bills: totalResult.count || 0,
    vpt_count: vptResult.count || 0,
    city_counts: cityCounts,
  };
}

export async function vptStartScan(
  city?: string,
  continuous = false
): Promise<{ status: string; message: string }> {
  const result = await invokeWorker<Record<string, unknown>>("scan.start", {
    city: city || null,
    continuous,
  });
  return toActionResult(
    result,
    `Scan trigger sent for ${city || "all cities"} (${continuous ? "continuous" : "single pass"}).`
  );
}

export async function vptStopScan(): Promise<{ status: string; message: string }> {
  const result = await invokeWorker<Record<string, unknown>>("scan.stop");
  return toActionResult(result, "Scan stop trigger sent.");
}

// Research
export async function vptGetResearchStatus(): Promise<VPTResearchStatus> {
  const [completed, failed, pending] = await Promise.all([
    supabase
      .from("bills")
      .select("apn", { count: "exact", head: true })
      .eq("research_status", "completed"),
    supabase
      .from("bills")
      .select("apn", { count: "exact", head: true })
      .eq("research_status", "failed"),
    supabase
      .from("bills")
      .select("apn", { count: "exact", head: true })
      .in("research_status", ["pending", "in_progress", "unchecked"]),
  ]);

  if (completed.error) throw new Error(completed.error.message);
  if (failed.error) throw new Error(failed.error.message);
  if (pending.error) throw new Error(pending.error.message);

  const totalCompleted = completed.count || 0;
  const totalFailed = failed.count || 0;
  const totalPending = pending.count || 0;
  const workerStatus = asRecord(
    await invokeWorker<Record<string, unknown>>("research.status", undefined, true)
  );
  const workerError = asString(workerStatus.error);

  return {
    is_running: asBoolean(workerStatus.is_running) ?? false,
    api_configured: workerError ? false : (asBoolean(workerStatus.api_configured) ?? true),
    current_apn: asString(workerStatus.current_apn),
    queue_length: asNumber(workerStatus.queue_length) ?? totalPending,
    completed: asNumber(workerStatus.completed) ?? 0,
    total_completed: asNumber(workerStatus.total_completed) ?? totalCompleted,
    total_pending: asNumber(workerStatus.total_pending) ?? totalPending,
    total_failed: asNumber(workerStatus.total_failed) ?? totalFailed,
  };
}

export async function vptStartResearch(
  apns: string[]
): Promise<{ status: string; message: string }> {
  if (!apns.length) {
    return { status: "ok", message: "No APNs provided." };
  }

  const result = toActionResult(
    await invokeWorker<Record<string, unknown>>("research.start", { apns }),
    `Research started for ${apns.length} properties.`
  );

  if (result.status === "ok") {
    const now = new Date().toISOString();
    const { error } = await supabase
      .from("bills")
      .update({ research_status: "pending", research_updated_at: now })
      .in("apn", apns);

    if (error) {
      throw new Error(error.message);
    }
  }

  return result;
}

export async function vptGetResearchReport(apn: string): Promise<{ apn: string; report: string }> {
  const { data, error } = await supabase
    .from("bills")
    .select("research_status,research_report_path,property_search_url,mailing_search_url,owner_details_url")
    .eq("apn", apn)
    .maybeSingle();

  if (error) {
    throw new Error(error.message);
  }

  if (!data) {
    throw new Error("Property not found");
  }

  const lines = [
    `APN: ${apn}`,
    `Research status: ${data.research_status || "unchecked"}`,
  ];

  if (data.research_report_path) {
    lines.push(`Stored report path: ${data.research_report_path}`);
  } else {
    lines.push("No report text is stored in Supabase for this APN yet.");
  }

  if (data.property_search_url) {
    lines.push(`Property search: ${data.property_search_url}`);
  }

  if (data.mailing_search_url) {
    lines.push(`Mailing search: ${data.mailing_search_url}`);
  }

  if (data.owner_details_url) {
    lines.push(`Owner details: ${data.owner_details_url}`);
  }

  return { apn, report: lines.join("\n") };
}

// Condition Scanner
export async function vptGetConditionStatus(): Promise<VPTConditionStatus> {
  const [scannedCountResult, poorCountResult, avgResult] = await Promise.all([
    supabase.from("bills").select("apn", { count: "exact", head: true }).not("condition_score", "is", null),
    supabase
      .from("bills")
      .select("apn", { count: "exact", head: true })
      .gte("condition_score", 7),
    supabase.from("bills").select("condition_score").not("condition_score", "is", null),
  ]);

  if (scannedCountResult.error) throw new Error(scannedCountResult.error.message);
  if (poorCountResult.error) throw new Error(poorCountResult.error.message);
  if (avgResult.error) throw new Error(avgResult.error.message);

  const scores = (avgResult.data || [])
    .map((row) => row.condition_score)
    .filter((value): value is number => typeof value === "number");

  const averageScore =
    scores.length > 0
      ? scores.reduce((sum, score) => sum + score, 0) / scores.length
      : null;
  const workerStatus = asRecord(
    await invokeWorker<Record<string, unknown>>("condition.status", undefined, true)
  );
  const workerError = asString(workerStatus.error);

  return {
    is_running: asBoolean(workerStatus.is_running) ?? false,
    api_configured: workerError ? false : (asBoolean(workerStatus.api_configured) ?? true),
    current_apn: asString(workerStatus.current_apn),
    total_scanned: scannedCountResult.count || 0,
    average_score: averageScore,
    poor_condition: poorCountResult.count || 0,
  };
}

export async function vptStartConditionScan(
  apns: string[]
): Promise<{ status: string; message: string }> {
  return toActionResult(
    await invokeWorker<Record<string, unknown>>("condition.start", { apns }),
    `Condition scan started for ${apns.length} properties.`
  );
}

export async function vptStartConditionScanAll(): Promise<{ status: string; message: string }> {
  return toActionResult(
    await invokeWorker<Record<string, unknown>>("condition.start_all"),
    "Condition scan started for unscanned properties."
  );
}

export async function vptGetConditionScore(
  apn: string
): Promise<{ apn: string; score: number; notes: string; updated_at: string; has_image: boolean }> {
  const { data, error } = await supabase
    .from("bills")
    .select("condition_score,condition_notes,condition_updated_at,streetview_image_path")
    .eq("apn", apn)
    .maybeSingle();

  if (error) {
    throw new Error(error.message);
  }

  if (!data || data.condition_score === null) {
    throw new Error("No condition score available");
  }

  return {
    apn,
    score: data.condition_score,
    notes: data.condition_notes || "",
    updated_at: data.condition_updated_at || "",
    has_image: Boolean(data.streetview_image_path),
  };
}

// PGE Scanner
export async function vptGetPgeStatus(): Promise<VPTPgeStatus> {
  const [totalResult, onResult, offResult] = await Promise.all([
    supabase.from("bills").select("apn", { count: "exact", head: true }),
    supabase.from("bills").select("apn", { count: "exact", head: true }).eq("power_status", "on"),
    supabase.from("bills").select("apn", { count: "exact", head: true }).eq("power_status", "off"),
  ]);

  if (totalResult.error) throw new Error(totalResult.error.message);
  if (onResult.error) throw new Error(onResult.error.message);
  if (offResult.error) throw new Error(offResult.error.message);

  const total = totalResult.count || 0;
  const on = onResult.count || 0;
  const off = offResult.count || 0;
  const unchecked = Math.max(total - on - off, 0);
  const workerStatus = asRecord(
    await invokeWorker<Record<string, unknown>>("pge.status", undefined, true)
  );

  return {
    is_running: asBoolean(workerStatus.is_running) ?? false,
    current_address: asString(workerStatus.current_address),
    total_power_on: asNumber(workerStatus.total_power_on) ?? on,
    total_power_off: asNumber(workerStatus.total_power_off) ?? off,
    total_unchecked: asNumber(workerStatus.total_unchecked) ?? unchecked,
  };
}

export async function vptStartPgeScan(
  apns?: string[]
): Promise<{ status: string; message: string }> {
  return toActionResult(
    await invokeWorker<Record<string, unknown>>("pge.start", { apns: apns || null }),
    apns?.length ? `PGE scan started for ${apns.length} properties.` : "PGE scan started."
  );
}

export async function vptStartPgeScanAll(): Promise<{ status: string; message: string }> {
  return toActionResult(
    await invokeWorker<Record<string, unknown>>("pge.start_all"),
    "PGE scan started for unchecked properties."
  );
}

export async function vptStopPgeScan(): Promise<{ status: string; message: string }> {
  return toActionResult(
    await invokeWorker<Record<string, unknown>>("pge.stop"),
    "PGE scan stop trigger sent."
  );
}

// Utility
export function vptGetStreetviewUrl(apn: string): string {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(apn)}`;
}

export function vptGetStreetviewImageUrlFromMarker(marker: {
  lat: number;
  lng: number;
  location: string;
}): string {
  return buildStreetviewImageUrl(marker.lat, marker.lng, marker.location);
}
