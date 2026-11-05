export interface Conversation {
  id: string;
  title: string;
  character_id?: string;
  image_gen_mode: 'none' | 'probable' | 'definitely';
  updated_at: string;
}

export interface Message {
  id?: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  image_paths?: string[];
  created_at?: string;
}

export interface ModelConfig {
  id: string;
  display_name: string;
  file_path: string;
  context_length: number;
  vision_supported: boolean;
  quantization?: string;
}

export interface Character {
  id: string;
  name: string;
  avatar_emoji: string;
  description?: string;
  system_prompt: string;
  voice_persona: string;
  temperature: number;
}
