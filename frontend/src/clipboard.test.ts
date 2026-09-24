// @vitest-environment jsdom

import { describe, expect, it, vi } from "vitest";
import { copyText } from "./clipboard";

describe("copyText", () => {
  it("uses the Clipboard API when available", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });

    await copyText("kubectl get pods");

    expect(writeText).toHaveBeenCalledWith("kubectl get pods");
  });

  it("falls back to document.execCommand", async () => {
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: undefined });
    const execCommand = vi.fn().mockReturnValue(true);
    Object.defineProperty(document, "execCommand", { configurable: true, value: execCommand });

    await copyText("kubectl get nodes");

    expect(execCommand).toHaveBeenCalledWith("copy");
  });
});
