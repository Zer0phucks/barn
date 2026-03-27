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
});
