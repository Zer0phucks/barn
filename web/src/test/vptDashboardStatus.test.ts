import { describe, expect, it, vi } from "vitest";

vi.mock("@/services/vptApi", () => ({
  vptGetScanStatus: vi.fn(),
  vptGetEnrichmentStatus: vi.fn(),
}));

import { getAutopilotHeaderStatus } from "@/components/admin/vpt/VPTDashboard";

describe("getAutopilotHeaderStatus", () => {
  it("returns online when worker status is reachable", () => {
    expect(getAutopilotHeaderStatus({ reachable: true })).toEqual({
      tone: "green",
      label: "Autopilot Online",
    });
  });

  it("returns offline when worker status is unreachable", () => {
    expect(getAutopilotHeaderStatus({ reachable: false })).toEqual({
      tone: "red",
      label: "Autopilot Offline",
    });
  });
});
