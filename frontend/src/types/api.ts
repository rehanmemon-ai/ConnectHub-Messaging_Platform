export type UUID = string;

export interface PublicUser {
  id: UUID;
  username: string;
  display_name: string;
  created_at: string;
}

export interface OwnUser extends PublicUser {
  email: string;
  updated_at: string;
}

export interface MembershipView {
  role: "owner" | "member";
  joined_at: string;
}

export interface Room {
  id: UUID;
  name: string;
  description: string;
  visibility: "public" | "private";
  membership: MembershipView | null;
  created_at: string;
}

export interface JoinedRoom {
  room: Room;
  role: "owner" | "member";
  joined_at: string;
}

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

export interface Message {
  id: UUID;
  room_id: UUID;
  sender: PublicUser;
  content: string;
  created_at: string;
}

export interface Member {
  user_id: UUID;
  username: string;
  display_name: string;
  role: "owner" | "member";
  joined_at: string;
  online: boolean;
  last_seen_at: string | null;
}

export interface Invitation {
  id: UUID;
  room_id: UUID;
  room_name: string;
  inviter_username: string;
  invitee_username: string;
  status: string;
  created_at: string;
  expires_at: string;
  responded_at: string | null;
}

export interface Notification {
  id: UUID;
  type: "room_invitation" | "room_membership_removed" | "message_mention" | string;
  room_id: UUID | null;
  actor_id: UUID | null;
  message_id: UUID | null;
  invitation_id: UUID | null;
  metadata: Record<string, unknown>;
  created_at: string;
  read_at: string | null;
}

export interface ReadReceipt {
  room_id: UUID;
  user: PublicUser;
  message_id: UUID;
  read_at: string;
}

export interface Summary {
  id: UUID;
  room_id: UUID;
  provider: string;
  model: string;
  prompt_version: string;
  content: string;
  source_start_id: UUID;
  source_end_id: UUID;
  source_message_count: number;
  source_truncated: boolean;
  input_characters: number;
  created_at: string;
  cached: boolean;
}

export interface EmbeddingStatus {
  total_messages: number;
  indexed_messages: number;
  pending_jobs: number;
  failed_jobs: number;
  provider: string;
  model: string;
  embedding_profile: string;
  candidate_limit: number;
  storage: string;
}

export interface SemanticResult {
  message: Message;
  similarity: number;
}

export interface SemanticSearchResponse {
  items: SemanticResult[];
  total_messages: number;
  indexed_messages: number;
  indexed_candidates: number;
  unindexed_messages: number;
  candidate_limit: number;
  candidate_window_truncated: boolean;
  failed_jobs: number;
  embedding_profile: string;
}

export interface ApiErrorShape {
  error: {
    code: string;
    message: string;
    details: Array<{ field?: string; code?: string; message?: string }>;
    request_id?: string;
  };
}

export type ConnectionState = "connecting" | "connected" | "reconnecting" | "disconnected";

export type ServerEvent =
  | { type: "connection.ready"; connection_id: UUID; user_id: UUID; subscriptions: UUID[] }
  | { type: "room.subscribed" | "room.unsubscribed"; room_id: UUID }
  | { type: "message.created" | "message.replayed"; message: Message }
  | { type: "typing.started"; room_id: UUID; user: PublicUser }
  | { type: "typing.stopped"; room_id: UUID; user_id: UUID }
  | {
      type: "presence.changed";
      room_id: UUID;
      user_id: UUID;
      status: "online" | "offline";
      connection_count: number;
    }
  | { type: "read_receipt.changed"; receipt: ReadReceipt }
  | { type: "notification.created"; notification_type: string; invitation_id?: UUID }
  | { type: "room.member_joined" | "room.member_removed"; room_id: UUID; user_id: UUID }
  | { type: "room.membership_removed" | "room.deleted"; room_id: UUID }
  | { type: "pong"; nonce: string; timestamp: string }
  | { type: "error"; error: { code: string; message: string; recoverable: boolean } };
