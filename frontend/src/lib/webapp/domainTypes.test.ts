import { describe, expect, it } from "vitest";

import {
  arrayField,
  recordArrayField,
  recordField,
  recordOrNull,
  stringField,
} from "./domainTypes";

describe("webapp domain type normalizers", () => {
  it("normalizes object values without accepting arrays", () => {
    expect(recordField({ id: 1 })).toEqual({ id: 1 });
    expect(recordField(["not", "a", "record"])).toEqual({});
    expect(recordOrNull({ id: 1 })).toEqual({ id: 1 });
    expect(recordOrNull(["not", "a", "record"])).toBeNull();
  });

  it("keeps arrays explicit and filters record arrays", () => {
    const source = [{ id: 1 }, null, "skip", ["skip"], { id: 2 }];

    expect(arrayField(source)).toBe(source);
    expect(arrayField({})).toEqual([]);
    expect(recordArrayField(source)).toEqual([{ id: 1 }, { id: 2 }]);
  });

  it("normalizes optional strings", () => {
    expect(stringField("ready")).toBe("ready");
    expect(stringField(42)).toBe("");
  });
});
