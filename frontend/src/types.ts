/**
 * Type definitions for TreePilot
 */

export interface Individual {
  id: string;
  firstName: string;
  lastName: string;
  fullName: string;
  gender: 'M' | 'F' | 'U';
  birthYear: number | null;
  deathYear: number | null;
  birthPlace: string | null;
}

export interface TreeNode extends Individual {
  children?: TreeNode[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  thinking?: string;
  toolStatus?: string;
  timestamp: Date;
  isStreaming?: boolean;
  isThinking?: boolean;
}

export interface GedcomUploadResponse {
  message: string;
  individual_count: number;
  individuals: Individual[];
}

export interface TreeResponse {
  tree: TreeNode | null;
  root_person: TreeNode | null;
}

export interface PersonMetadata {
  id: string;
  firstName: string;
  lastName: string;
  fullName: string;
  gender: 'M' | 'F' | 'U';
  birthYear: number | null;
  deathYear: number | null;
  birthPlace: string | null;
  deathPlace: string | null;
  occupation: string | null;
  notes: string[];
  customFacts: Record<string, string[]>;
}

// Chat session for multi-session support
export interface ChatSession {
  id: string;
  name: string;
  messages: ChatMessage[];
  personContext: Individual | null;
  createdAt: number;
}
