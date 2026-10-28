import { describe, expect, it } from "vitest";
import {
  BLOOD_GROUPS, isEmail, isPhone, validateRequestForm,
} from "../utils/validate";

describe("validateRequestForm", () => {
  const valid = {
    blood_group: "B+", city: "Hyderabad", locality: "Gachibowli",
    hospital: "Demo Hospital", units: "2", urgency: "urgent",
    needed_by: new Date(Date.now() + 24 * 3600 * 1000).toISOString().slice(0, 16),
    requester_name: "Rahul Mehta", contact_value: "+919812345678",
    contact_method: "phone",
  };

  it("accepts a valid form", () => {
    expect(validateRequestForm(valid)).toEqual({});
  });

  it("rejects invalid blood groups", () => {
    const errors = validateRequestForm({ ...valid, blood_group: "Z+" });
    expect(errors.blood_group).toBeTruthy();
  });

  it("rejects zero and negative units", () => {
    expect(validateRequestForm({ ...valid, units: "0" }).units).toBeTruthy();
    expect(validateRequestForm({ ...valid, units: "-1" }).units).toBeTruthy();
    expect(validateRequestForm({ ...valid, units: "2.5" }).units).toBeTruthy();
  });

  it("requires a future needed_by date", () => {
    const past = new Date(Date.now() - 3600 * 1000).toISOString().slice(0, 16);
    expect(validateRequestForm({ ...valid, needed_by: past }).needed_by).toContain("future");
  });

  it("requires hospital, city and coordinator", () => {
    const errors = validateRequestForm({ ...valid, hospital: "", city: "", requester_name: "" });
    expect(errors.hospital).toBeTruthy();
    expect(errors.city).toBeTruthy();
    expect(errors.requester_name).toBeTruthy();
  });
});

describe("contact validators", () => {
  it("detects valid emails and phones", () => {
    expect(isEmail("test@example.demo")).toBe(true);
    expect(isEmail("not-an-email")).toBe(false);
    expect(isPhone("+919812345678")).toBe(true);
    expect(isPhone("12345")).toBe(false);
  });

  it("covers all eight blood groups", () => {
    expect(BLOOD_GROUPS).toHaveLength(8);
  });
});
