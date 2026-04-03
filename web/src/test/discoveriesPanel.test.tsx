import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import React from "react";

vi.mock("@/services/vptApi", () => ({
  getDiscoveries: vi.fn(),
  acknowledgeDiscoveries: vi.fn(),
}));

import { getDiscoveries, acknowledgeDiscoveries } from "@/services/vptApi";
import type { VPTDiscovery } from "@/services/vptApi";
import DiscoveriesPanel from "@/components/admin/vpt/DiscoveriesPanel";

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

describe("DiscoveriesPanel component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when getDiscoveries returns zero total", async () => {
    vi.mocked(getDiscoveries).mockResolvedValue({ discoveries: [], total: 0 });

    const { container } = render(<DiscoveriesPanel />);

    await waitFor(() => {
      expect(getDiscoveries).toHaveBeenCalledTimes(1);
    });

    // After loading completes with total === 0, component returns null
    expect(container.firstChild).toBeNull();
  });

  it("renders APN and address when a discovery is returned", async () => {
    const discovery = makeDiscovery("001-001-001", {
      location_of_property: "123 Main St",
    });
    vi.mocked(getDiscoveries).mockResolvedValue({ discoveries: [discovery], total: 1 });

    render(<DiscoveriesPanel />);

    await waitFor(() => {
      expect(screen.getByText("001-001-001")).toBeInTheDocument();
    });

    expect(screen.getByText("123 Main St")).toBeInTheDocument();
  });

  it("calls acknowledgeDiscoveries with the correct APN when Ack is clicked", async () => {
    const discovery = makeDiscovery("002-002-002");
    vi.mocked(getDiscoveries).mockResolvedValue({ discoveries: [discovery], total: 1 });
    vi.mocked(acknowledgeDiscoveries).mockResolvedValue({ status: "ok", updated: 1 });

    render(<DiscoveriesPanel />);

    const ackBtn = await screen.findByTestId("ack-btn-002-002-002");
    fireEvent.click(ackBtn);

    await waitFor(() => {
      expect(acknowledgeDiscoveries).toHaveBeenCalledWith(["002-002-002"]);
    });
  });

  it("calls getDiscoveries again after Ack to refresh", async () => {
    const discovery = makeDiscovery("003-003-003");
    vi.mocked(getDiscoveries).mockResolvedValue({ discoveries: [discovery], total: 1 });
    vi.mocked(acknowledgeDiscoveries).mockResolvedValue({ status: "ok", updated: 1 });

    render(<DiscoveriesPanel />);

    const ackBtn = await screen.findByTestId("ack-btn-003-003-003");
    fireEvent.click(ackBtn);

    await waitFor(() => {
      // Initial load call + refresh call after ack
      expect(getDiscoveries).toHaveBeenCalledTimes(2);
    });
  });
});
