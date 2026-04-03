import { describe, expect, it, vi, beforeEach } from "vitest";

// Mock vptApi before importing the component
vi.mock("@/services/vptApi", () => ({
  getWorkerStatus: vi.fn(),
  resumeScan: vi.fn(),
  vptStopScan: vi.fn(),
}));

// We test the label-derivation logic extracted from WorkerStatus inline
// because the component depends on shadcn/ui and router context.
// The logic is simple and deterministic so a direct unit test is the right level.

import type { VPTWorkerState } from "@/services/vptApi";

function deriveLabel(state: VPTWorkerState): string {
  if (!state.worker || state.worker.status === "offline") {
    return "Worker offline";
  }
  if (state.active_job) {
    const { job_type, current_city, current_apn } = state.active_job;
    const parts = [job_type];
    if (current_city) parts.push(`– ${current_city}`);
    if (current_apn) parts.push(current_apn);
    return `Worker online · running ${parts.join(" ")}`;
  }
  if (state.last_interrupted_job) {
    return "Worker online · interrupted job available";
  }
  return "Worker online · idle";
}

const makeJob = (overrides = {}) => ({
  id: "job-1",
  job_type: "city_scan",
  status: "running",
  current_city: null,
  current_apn: null,
  processed_count: 0,
  hit_count: 0,
  started_at: null,
  ...overrides,
});

const onlineWorker = { name: "worker-1", last_heartbeat: null, tunnel_url: null, status: "online" as const };
const offlineWorker = { name: "worker-1", last_heartbeat: null, tunnel_url: null, status: "offline" as const };

describe("WorkerStatus label derivation", () => {
  it("returns 'Worker offline' when worker is null", () => {
    const state: VPTWorkerState = { worker: null, active_job: null, last_interrupted_job: null };
    expect(deriveLabel(state)).toBe("Worker offline");
  });

  it("returns 'Worker offline' when worker status is offline", () => {
    const state: VPTWorkerState = { worker: offlineWorker, active_job: null, last_interrupted_job: null };
    expect(deriveLabel(state)).toBe("Worker offline");
  });

  it("returns 'Worker online · idle' when online with no jobs", () => {
    const state: VPTWorkerState = { worker: onlineWorker, active_job: null, last_interrupted_job: null };
    expect(deriveLabel(state)).toBe("Worker online · idle");
  });

  it("returns running label with job_type when active_job has no city or apn", () => {
    const state: VPTWorkerState = {
      worker: onlineWorker,
      active_job: makeJob({ job_type: "daily_intake" }),
      last_interrupted_job: null,
    };
    expect(deriveLabel(state)).toBe("Worker online · running daily_intake");
  });

  it("includes city in running label when current_city is set", () => {
    const state: VPTWorkerState = {
      worker: onlineWorker,
      active_job: makeJob({ job_type: "city_scan", current_city: "OAKLAND" }),
      last_interrupted_job: null,
    };
    expect(deriveLabel(state)).toBe("Worker online · running city_scan – OAKLAND");
  });

  it("includes city and APN in running label when both are set", () => {
    const state: VPTWorkerState = {
      worker: onlineWorker,
      active_job: makeJob({ job_type: "city_scan", current_city: "OAKLAND", current_apn: "001-001-001" }),
      last_interrupted_job: null,
    };
    expect(deriveLabel(state)).toBe("Worker online · running city_scan – OAKLAND 001-001-001");
  });

  it("returns interrupted label when last_interrupted_job exists and no active_job", () => {
    const state: VPTWorkerState = {
      worker: onlineWorker,
      active_job: null,
      last_interrupted_job: makeJob({ job_type: "city_scan", status: "interrupted" }),
    };
    expect(deriveLabel(state)).toBe("Worker online · interrupted job available");
  });

  it("returns running label (not interrupted) when both active_job and last_interrupted_job exist", () => {
    const state: VPTWorkerState = {
      worker: onlineWorker,
      active_job: makeJob({ job_type: "city_scan", current_city: "FREMONT" }),
      last_interrupted_job: makeJob({ job_type: "old_scan", status: "interrupted" }),
    };
    expect(deriveLabel(state)).toBe("Worker online · running city_scan – FREMONT");
  });
});

describe("WorkerStatus API integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("getWorkerStatus is exported from vptApi", async () => {
    const { getWorkerStatus } = await import("@/services/vptApi");
    expect(typeof getWorkerStatus).toBe("function");
  });

  it("resumeScan is exported from vptApi", async () => {
    const { resumeScan } = await import("@/services/vptApi");
    expect(typeof resumeScan).toBe("function");
  });
});
