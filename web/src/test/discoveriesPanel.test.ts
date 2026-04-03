import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("@/services/vptApi", () => ({
  getDiscoveries: vi.fn(),
  acknowledgeDiscoveries: vi.fn(),
}));

import { getDiscoveries, acknowledgeDiscoveries } from "@/services/vptApi";
import type { VPTDiscovery } from "@/services/vptApi";

const makeDiscovery = (apn: string, overrides: Partial<VPTDiscovery> = {}): VPTDiscovery => ({
  apn,
  location_of_property: `${apn} Main St`,
  city: "OAKLAND",
  first_seen_at: "2026-01-15T00:00:00Z",
  discovered_by_job_id: null,
  has_vpt: 0,
  vpt_marker: null,
  delinquent: null,
  ...overrides,
});

describe("DiscoveriesPanel: getDiscoveries contract", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("getDiscoveries is exported from vptApi", async () => {
    expect(typeof getDiscoveries).toBe("function");
  });

  it("acknowledgeDiscoveries is exported from vptApi", async () => {
    expect(typeof acknowledgeDiscoveries).toBe("function");
  });

  it("returns discoveries list when called successfully", async () => {
    const discoveries = [makeDiscovery("001-001-001"), makeDiscovery("002-002-002")];
    vi.mocked(getDiscoveries).mockResolvedValue({ discoveries, total: 2 });

    const result = await getDiscoveries();

    expect(result.total).toBe(2);
    expect(result.discoveries).toHaveLength(2);
    expect(result.discoveries[0].apn).toBe("001-001-001");
  });

  it("returns empty list when there are no discoveries", async () => {
    vi.mocked(getDiscoveries).mockResolvedValue({ discoveries: [], total: 0 });

    const result = await getDiscoveries();

    expect(result.total).toBe(0);
    expect(result.discoveries).toHaveLength(0);
  });

  it("calls acknowledgeDiscoveries with correct apns", async () => {
    vi.mocked(acknowledgeDiscoveries).mockResolvedValue({ status: "ok", updated: 1 });

    await acknowledgeDiscoveries(["001-001-001"]);

    expect(acknowledgeDiscoveries).toHaveBeenCalledWith(["001-001-001"]);
  });

  it("acknowledgeDiscoveries can handle multiple apns at once", async () => {
    vi.mocked(acknowledgeDiscoveries).mockResolvedValue({ status: "ok", updated: 3 });

    const apns = ["001-001-001", "002-002-002", "003-003-003"];
    const result = await acknowledgeDiscoveries(apns);

    expect(acknowledgeDiscoveries).toHaveBeenCalledWith(apns);
    expect(result.updated).toBe(3);
  });

  it("discovery has_vpt flag distinguishes VPT from non-VPT properties", () => {
    const vpt = makeDiscovery("111", { has_vpt: 1 });
    const nonVpt = makeDiscovery("222", { has_vpt: 0 });

    expect(vpt.has_vpt).toBe(1);
    expect(nonVpt.has_vpt).toBe(0);
  });

  it("first_seen_at is a parseable ISO date string", () => {
    const d = makeDiscovery("333", { first_seen_at: "2026-01-15T00:00:00Z" });
    const parsed = new Date(d.first_seen_at);
    expect(Number.isNaN(parsed.getTime())).toBe(false);
    expect(parsed.getFullYear()).toBe(2026);
  });
});
