import { describe, expect, it, vi } from "vitest";

vi.mock("@/integrations/supabase/client", () => ({
  supabase: {
    from: vi.fn(),
    rpc: vi.fn(),
    functions: { invoke: vi.fn() },
    auth: { getSession: vi.fn() },
  },
}));

import { mapRpcRowToProperty } from "@/services/vptApi";

describe("mapRpcRowToProperty", () => {
  it("preserves added_at from rpc rows", () => {
    const property = mapRpcRowToProperty(
      {
        apn: "123",
        pdf_file: null,
        bill_url: null,
        parcel_number: null,
        tracer_number: null,
        location_of_property: "123 Main St",
        tax_year: null,
        last_payment: null,
        delinquent: 0,
        power_status: "off",
        has_vpt: 1,
        vpt_marker: "MEAS-W OAKLAND VPT",
        city: "OAKLAND",
        condition_score: null,
        condition_notes: null,
        streetview_image_path: null,
        property_search_url: null,
        mailing_search_url: null,
        research_status: "unchecked",
        added_at: "2026-03-26T04:00:00Z",
        row_json: {
          SitusAddress: "123 Main St",
          SitusCity: "Oakland",
          MailingAddress: "PO Box 1",
          CENTROID_X: 0,
          CENTROID_Y: 0,
        },
        situs_zip: "94601",
      },
      new Set()
    );

    expect(property.added_at).toBe("2026-03-26T04:00:00Z");
  });
});
