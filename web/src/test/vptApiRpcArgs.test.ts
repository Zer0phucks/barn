import { beforeEach, describe, expect, it, vi } from "vitest";

const { rpcMock, selectMock, fromMock } = vi.hoisted(() => {
  const select = vi.fn();
  const from = vi.fn(() => ({ select }));
  const rpc = vi.fn();
  return {
    rpcMock: rpc,
    selectMock: select,
    fromMock: from,
  };
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

describe("vptGetProperties rpc args", () => {
  beforeEach(() => {
    rpcMock.mockReset();
    fromMock.mockClear();
    selectMock.mockReset();

    selectMock.mockResolvedValue({ data: [], error: null });
    rpcMock.mockResolvedValue({ data: { rows: [], total: 0 }, error: null });
  });

  it("includes p_owner_name to disambiguate overloaded rpc signatures", async () => {
    await vptGetProperties({ q: "oakland" });

    expect(rpcMock).toHaveBeenCalledWith(
      "get_bills_filtered",
      expect.objectContaining({
        p_owner_name: "",
      })
    );
  });

  it("passes p_new: 1 when filters.new is '1'", async () => {
    await vptGetProperties({ new: "1" });

    expect(rpcMock).toHaveBeenCalledWith(
      "get_bills_filtered",
      expect.objectContaining({
        p_new: 1,
      })
    );
  });

  it("does not include p_new when filters.new is not set", async () => {
    await vptGetProperties({ q: "oakland" });

    const args = rpcMock.mock.calls[0][1] as Record<string, unknown>;
    expect(args).not.toHaveProperty("p_new");
  });
});
