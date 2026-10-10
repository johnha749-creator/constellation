export const CONFLICT_TYPE_LABELS = {
  allergy: "Allergy",
  duplicate_therapy: "Duplicate therapy",
  interaction: "Drug interaction",
  condition: "Drug vs condition",
  dose_mismatch: "Dose mismatch",
};

export const SEVERITY_RANK = { low: 1, moderate: 2, high: 3 };

// Role permissions, as named by the backend (auth.py).
export const VIEW_CLINICAL = "view_clinical";
export const REVIEW_MATCHES = "review_matches";
export const REVEAL_CONTACTS = "reveal_contacts";
export const CONNECT_HOSPITALS = "connect_hospitals";

const HOSPITAL_PALETTE = ["#7cc6fe", "#f4a7ff", "#9ef0c4", "#ffd29d", "#a5b4fc"];

/** [{id, name}] from /api/hospitals -> {id: {id, name, color}}, colored in API order. */
export function withHospitalColors(hospitals) {
  return Object.fromEntries(
    hospitals.map((h, i) => [h.id, { ...h, color: HOSPITAL_PALETTE[i % HOSPITAL_PALETTE.length] }]),
  );
}
