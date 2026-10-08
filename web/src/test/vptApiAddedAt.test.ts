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

  it("defaults added_at to 31 days ago when missing from rpc row", () => {
    const property = mapRpcRowToProperty(
      {
        apn: "456",
        pdf_file: null,
        bill_url: null,
        parcel_number: null,
        tracer_number: null,
        location_of_property: "456 Main St",
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
        added_at: null,
        row_json: null,
        situs_zip: "94601",
      },
      new Set()
    );

    expect(property.added_at).toBeTruthy();
    // Verify it is not marked as new (diff > 30 days)
    expect(isWithinDays(property.added_at, 30)).toBe(false);
  });
});

import { isWithinDays, formatAddedAt } from "@/services/vptApi";

describe("isWithinDays", () => {
  it("returns true for a date within the last 30 days", () => {
    const recent = new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString();
    expect(isWithinDays(recent, 30)).toBe(true);
  });

  it("returns false for a date older than 30 days", () => {
    const old = new Date(Date.now() - 35 * 24 * 60 * 60 * 1000).toISOString();
    expect(isWithinDays(old, 30)).toBe(false);
  });

  it("returns false for null or empty dates", () => {
    expect(isWithinDays(null)).toBe(false);
    expect(isWithinDays("")).toBe(false);
    expect(isWithinDays(undefined)).toBe(false);
  });
});

describe("formatAddedAt", () => {
  it("formats valid iso date string", () => {
    expect(formatAddedAt("2026-01-15T00:00:00Z")).toMatch(/\d{1,2}\/\d{1,2}\/\d{4}/);
  });

  it("returns formatted 31-days-ago date for null or undefined", () => {
    const fallback = formatAddedAt(null);
    expect(fallback).toMatch(/\d{1,2}\/\d{1,2}\/\d{4}/);
  });
});
