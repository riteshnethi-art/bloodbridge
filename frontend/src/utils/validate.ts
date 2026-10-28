// Client-side validation shared by forms and unit tests.
export interface RequestFormFields {
  blood_group: string;
  city: string;
  locality: string;
  hospital: string;
  units: string | number;
  urgency: string;
  needed_by: string; // datetime-local string
  requester_name: string;
  contact_value: string;
  contact_method: string;
}

export const BLOOD_GROUPS = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"] as const;
export const URGENCIES = ["critical", "urgent", "routine"] as const;

export function validateRequestForm(f: Partial<RequestFormFields>): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!f.blood_group || !BLOOD_GROUPS.includes(f.blood_group as (typeof BLOOD_GROUPS)[number])) {
    errors.blood_group = "Select a blood group";
  }
  const city = (f.city ?? "").trim();
  if (city.length < 2 || city.length > 120) errors.city = "City is required (2-120 characters)";
  const hospital = (f.hospital ?? "").trim();
  if (hospital.length < 2 || hospital.length > 200) {
    errors.hospital = "Hospital or collection location is required";
  }
  const units = Number(f.units);
  if (!Number.isInteger(units) || units < 1 || units > 20) {
    errors.units = "Units must be a whole number between 1 and 20";
  }
  if (!URGENCIES.includes((f.urgency ?? "") as (typeof URGENCIES)[number])) {
    errors.urgency = "Select an urgency level";
  }
  if (!f.needed_by) {
    errors.needed_by = "Needed-by date and time is required";
  } else {
    const when = new Date(f.needed_by);
    if (Number.isNaN(when.getTime())) {
      errors.needed_by = "Enter a valid date and time";
    } else if (when.getTime() <= Date.now()) {
      errors.needed_by = "Needed-by must be in the future";
    }
  }
  const name = (f.requester_name ?? "").trim();
  if (name.length < 2 || name.length > 120) errors.requester_name = "Coordinator name is required";
  const contact = (f.contact_value ?? "").trim();
  if (contact.length < 5 || contact.length > 160) {
    errors.contact_value = "A phone number or email is required";
  }
  return errors;
}

export function isEmail(value: string): boolean {
  return /^[\w.+-]+@[\w-]+\.[\w.-]+$/.test(value.trim());
}

export function isPhone(value: string): boolean {
  const digits = value.replace(/[^\d]/g, "");
  return digits.length >= 10 && digits.length <= 15;
}
