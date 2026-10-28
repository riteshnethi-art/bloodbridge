// Shared API types (mirrors backend serializers).

export interface User {
  id: number;
  name: string;
  email: string;
  phone: string | null;
  role: "requester" | "donor" | "admin";
  email_verified: boolean;
  onboarding_completed: boolean;
  created_at: string;
}

export interface DonorProfile {
  id: number;
  user_id: number;
  blood_group: string;
  city: string;
  locality: string;
  preferred_contact: string;
  availability: "available" | "maybe" | "unavailable";
  last_confirmed_at: string;
  discoverable: boolean;
  allow_direct_contact: boolean;
  can_receive_urgent: boolean;
  verified: boolean;
}

export interface DonorPublic {
  donor_id: number;
  blood_group: string;
  city: string;
  locality: string;
  approx_distance_km: number | null;
  availability: string;
  last_confirmed_at: string | null;
  verified: boolean;
  preferred_contact: string;
  can_receive_urgent: boolean;
}

export interface BloodRequest {
  public_id: string;
  blood_group: string;
  city: string;
  locality: string;
  hospital: string;
  units: number;
  urgency: "critical" | "urgent" | "routine";
  needed_by: string;
  status: string;
  notes: string;
  created_at: string;
  closed_reason: string | null;
  requester_name?: string;
  contact_method?: string;
  contact_value?: string;
  compatibility_notice: string;
}

export interface Match {
  id: number;
  donor: DonorPublic;
  exact_group: boolean;
  same_city: boolean;
  score: number;
  explanation: string;
  created_at: string;
}

export interface ContactEvent {
  id: number;
  request_public_id: string;
  method: string;
  status: string;
  token: string;
  donor_message: string;
  created_at: string;
  responded_at: string | null;
  blood_group: string;
  city: string;
  locality: string;
  hospital: string;
  urgency: string;
  needed_by: string;
  units: number;
  requester_name?: string;
  requester_contact?: string;
  requester_contact_method?: string;
  donor?: DonorPublic;
  donor_contact_revealed?: boolean;
  donor_contact?: string;
}

export interface RewardOffer {
  id: number;
  offer_ref: string;
  partner_name: string;
  is_demo_partner: boolean;
  partner_label: string;
  title: string;
  description: string;
  category: string;
  eligibility_rules: string;
  quantity: number;
  remaining: number;
  valid_from: string | null;
  valid_to: string | null;
  redemption_instructions: string;
  terms: string;
  status: string;
  claim_count?: number;
}

export interface Recognition {
  id: number;
  kind: "badge" | "certificate" | "educational";
  title: string;
  description: string;
  reference: string;
  source: string;
  issued_at: string;
}

export interface ClaimItem {
  claim_code: string;
  status: string;
  claimed_at: string;
  redeemed_at: string | null;
  offer: {
    offer_ref: string;
    title: string;
    partner_name: string;
    is_demo_partner: boolean;
    terms: string;
    redemption_instructions: string;
  };
}

export interface Wallet {
  badges: Recognition[];
  certificates: Recognition[];
  education: Recognition[];
  claims: ClaimItem[];
  education_modules_available: { key: string; title: string; description: string }[];
}

export interface ReferralStats {
  code: string;
  link: string;
  link_visits_measured: number;
  registrations: number;
  contact_verified: number;
  pending: number;
  under_review: number;
  approved: number;
  rejected: number;
  eligible: number;
}

export interface ReferralHistoryItem {
  id: number;
  referred_name: string | null;
  status: string;
  source: string;
  flag_reasons: string[];
  attributed_at: string;
  events: { type: string; at: string; verification: string }[];
  reward: { type: string; status: string } | null;
}

export interface Campaign {
  id: number;
  name: string;
  description: string;
  start_at: string | null;
  end_at: string | null;
  eligible_event: string;
  reward_type: string;
  eligibility_rules: string;
  terms: string;
  status: string;
}

export interface Notification {
  id: number;
  type: string;
  title: string;
  body: string;
  link: string;
  read: boolean;
  created_at: string;
}

export interface AssistantProposal {
  blood_group: string;
  city: string;
  locality: string;
  hospital: string;
  units: number;
  urgency: string;
  needed_by: string;
  requester_name: string;
  contact_value: string;
  contact_method: string;
  notes: string;
}

export interface AssistantResponse {
  reply: string;
  chips: string[];
  proposal: AssistantProposal | null;
  awaiting: string;
  done: boolean;
  request_public_id: string | null;
  mode: string;
  disclaimer: string;
}
