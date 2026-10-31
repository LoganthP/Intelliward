import { describe, expect, it } from "vitest";
import { duration, pretty } from "./format";

describe("format", () => {
  it("formats durations", () => {
    expect(duration(45)).toBe("45s");
    expect(duration(420)).toBe("7m 00s");
    expect(duration(3720)).toBe("1h 2m");
  });
  it("labels statuses", () => {
    expect(pretty("review_required")).toBe("Needs review");
    expect(pretty("custom_state")).toBe("Custom state");
  });
});
