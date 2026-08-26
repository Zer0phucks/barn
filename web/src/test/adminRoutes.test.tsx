import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/pages/AdminLogin", () => ({
  default: () => <div>Admin login route</div>,
}));

vi.mock("@/pages/AdminDashboard", () => ({
  default: () => <div>Admin dashboard route</div>,
}));

import App from "@/App";

describe("admin routes", () => {
  afterEach(() => {
    window.history.pushState({}, "", "/");
  });

  it("renders the admin login inside the Vercel-hosted SPA", () => {
    window.history.pushState({}, "", "/admin");

    render(<App />);

    expect(screen.getByText("Admin login route")).toBeInTheDocument();
  });

  it("renders the admin dashboard inside the Vercel-hosted SPA", () => {
    window.history.pushState({}, "", "/admin/dashboard");

    render(<App />);

    expect(screen.getByText("Admin dashboard route")).toBeInTheDocument();
  });
});
