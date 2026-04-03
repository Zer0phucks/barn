import { describe, expect, it, vi, beforeEach } from "vitest";

const { rpcMock, selectMock, fromMock } = vi.hoisted(() => {
  const select = vi.fn();
  const from = vi.fn(() => ({ select }));
  const rpc = vi.fn();
  return { rpcMock: rpc, selectMock: select, fromMock: from };
});

vi.mock("@/integrations/supabase/client", () => ({
  supabase: {
    from: fromMock,
    rpc: rpcMock,
    functions: { invoke: vi.fn() },
    auth: { getSession: vi.fn() },
  },
}));

import { vptGetProperties } from "@/services/vptApi";

describe("New filter chip behaviour", () => {
  beforeEach(() => {
    rpcMock.mockReset();
    fromMock.mockClear();
    selectMock.mockReset();
    selectMock.mockResolvedValue({ data: [], error: null, count: 0 });
    rpcMock.mockResolvedValue({ data: { rows: [], total: 0 }, error: null });
  });

  it("passes p_new: 1 to RPC when new filter is '1'", async () => {
    await vptGetProperties({ new: "1" });

    expect(rpcMock).toHaveBeenCalledWith(
      "get_bills_filtered",
      expect.objectContaining({ p_new: 1 })
    );
  });

  it("does NOT include p_new when new filter is not set", async () => {
    await vptGetProperties({});

    const args = rpcMock.mock.calls[0][1] as Record<string, unknown>;
    expect(args).not.toHaveProperty("p_new");
  });

  it("does NOT include p_new when new filter is empty string", async () => {
    await vptGetProperties({ new: "" });

    const args = rpcMock.mock.calls[0][1] as Record<string, unknown>;
    expect(args).not.toHaveProperty("p_new");
  });

  it("does NOT include p_new when new filter is '0'", async () => {
    await vptGetProperties({ new: "0" });

    const args = rpcMock.mock.calls[0][1] as Record<string, unknown>;
    expect(args).not.toHaveProperty("p_new");
  });

  it("VPTFilters type includes a 'new' key", async () => {
    // Type-level check: this would fail to compile if 'new' is not in VPTFilters
    const filters: import("@/services/vptApi").VPTFilters = { new: "1" };
    expect(filters.new).toBe("1");
  });
});
