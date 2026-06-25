/** Member management contracts — mirrors app/schemas/member.py */

export interface MemberCreate {
  email: string;
  name: string;
}

export interface MemberCreated {
  user_id: string;
  membership_id: string;
  status: "pending";
}

export interface MemberRead {
  user_id: string;
  membership_id: string;
  email: string;
  name: string | null;
  role: string;
  status: "pending" | "accepted";
  created_at: string;
}

export interface MemberListResponse {
  items: MemberRead[];
  next_cursor: string | null;
}
