import { serve } from "https://deno.land/std@0.190.0/http/server.ts";

const defaultAllowedOrigins = [
  "http://localhost:5173",
  "http://127.0.0.1:5173",
  "http://localhost:8080",
  "http://127.0.0.1:8080",
  "https://barnhousing.org",
  "https://www.barnhousing.org",
];

const configuredAllowedOrigins = (Deno.env.get("ALLOWED_ORIGINS") || "")
  .split(",")
  .map((value) => value.trim())
  .filter(Boolean);

const allowedOrigins = new Set([
  ...defaultAllowedOrigins,
  ...configuredAllowedOrigins,
]);

const isAllowedOrigin = (origin: string | null) => {
  if (!origin) {
    return true;
  }

  return allowedOrigins.has(origin);
};

type WorkerRoute = {
  method: "GET" | "POST";
  path: string;
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

const extractErrorMessage = (value: unknown): string => {
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    if (typeof record.error === "string" && record.error) {
      return record.error;
    }
    if (typeof record.message === "string" && record.message) {
      return record.message;
    }
  }
  return "Worker request failed.";
};

serve(async (req) => {
  const origin = req.headers.get("origin");
  const corsHeaders = {
    "Access-Control-Allow-Origin": origin || "*",
    "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Vary": "Origin",
  };

  if (req.method === "OPTIONS") {
    if (!isAllowedOrigin(origin)) {
      return new Response(JSON.stringify({ error: "Origin not allowed." }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 403,
      });
    }
    return new Response(null, { headers: corsHeaders });
  }

  if (!isAllowedOrigin(origin)) {
    return new Response(
      JSON.stringify({ error: "Origin not allowed for scanner control." }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 403,
      }
    );
  }

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed." }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 405,
    });
  }

  const workerBaseUrl = (Deno.env.get("VPT_WORKER_BASE_URL") || "")
    .trim()
    .replace(/\/+$/, "");

  if (!workerBaseUrl) {
    return new Response(
      JSON.stringify({
        ok: false,
        error:
          "Scanner worker is not configured. Set VPT_WORKER_BASE_URL (and optionally VPT_WORKER_API_KEY).",
      }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 503,
      }
    );
  }

  let body: { action?: string; payload?: Record<string, unknown> } = {};
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ ok: false, error: "Invalid JSON body." }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 400,
    });
  }

  const action = body.action?.trim() || "";
  const route = workerRoutes[action];

  if (!route) {
    return new Response(
      JSON.stringify({ ok: false, error: `Unsupported scanner action: ${action}` }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 400,
      }
    );
  }

  const workerApiKey = (Deno.env.get("VPT_WORKER_API_KEY") || "").trim();
  const headers: HeadersInit = {
    Accept: "application/json",
  };

  if (route.method === "POST") {
    headers["Content-Type"] = "application/json";
  }

  if (workerApiKey) {
    headers["X-API-Key"] = workerApiKey;
  }

  const workerUrl = `${workerBaseUrl}${route.path}`;

  try {
    const response = await fetch(workerUrl, {
      method: route.method,
      headers,
      body: route.method === "POST" ? JSON.stringify(body.payload || {}) : undefined,
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
      return new Response(
        JSON.stringify({
          ok: false,
          status: response.status,
          error: extractErrorMessage(data),
          data,
        }),
        {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
          status: response.status,
        }
      );
    }

    return new Response(
      JSON.stringify({
        ok: true,
        status: response.status,
        data,
      }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 200,
      }
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown worker error.";
    return new Response(
      JSON.stringify({
        ok: false,
        error: `Unable to reach scanner worker: ${message}`,
      }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 502,
      }
    );
  }
});
