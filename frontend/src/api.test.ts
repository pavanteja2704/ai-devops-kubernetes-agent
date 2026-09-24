// @vitest-environment jsdom

import { describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { api, loadClusterData } from "./api";

describe("frontend API client", () => {
  it("uses the configured backend and requests all dashboard telemetry", async () => {
    const responses = {
      "/api/health": { status: "healthy" },
      "/api/kubernetes/status": { available: true, message: "online", context: "gke" },
      "/api/kubernetes/pods": [],
      "/api/kubernetes/deployments": [],
      "/api/kubernetes/services": [],
      "/api/kubernetes/nodes": [],
      "/api/kubernetes/events": [],
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => Promise.resolve({
      ok: true,
      json: async () => responses[new URL(String(input), "http://frontend.test").pathname as keyof typeof responses],
    } as Response));
    vi.stubGlobal("fetch", fetchMock);

    const data = await loadClusterData();

    expect(data.status.context).toBe("gke");
    expect(fetchMock).toHaveBeenCalledTimes(7);
  });

  it("posts an analysis question as JSON", async () => {
    const fetchMock = vi.fn(() => Promise.resolve({
      ok: true,
      json: async () => ({ summary: "Healthy" }),
    } as Response));
    vi.stubGlobal("fetch", fetchMock);

    await api.analyze("Check the cluster");

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/analyze"), expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ question: "Check the cluster" }),
    }));
  });
});
