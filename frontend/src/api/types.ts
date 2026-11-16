import { z } from 'zod';

export const courseSchema = z.object({ id: z.string(), name: z.string() });
export const lectureSchema = z.object({
  id: z.string(), course_id: z.string(), title: z.string(), filename: z.string(),
  source_id: z.string(), state: z.enum(['available', 'indexing', 'ready', 'error']),
  error: z.string().nullable().optional(),
});
export const sourceSchema = z.object({
  chunk_id: z.string(), lecture_id: z.string(), filename: z.string(),
  page: z.number().int().positive(), source_id: z.string(),
});
export const evidenceSchema = sourceSchema.extend({ text: z.string() });
export const toolEventSchema = z.object({
  name: z.string(), arguments: z.record(z.string(), z.union([z.string(), z.number().int(), z.null()])),
  evidence: z.array(sourceSchema),
});
export const messageSchema = z.object({
  role: z.enum(['user', 'assistant']), content: z.string(),
  sources: z.array(sourceSchema).default([]), tool_events: z.array(toolEventSchema).default([]),
});
export const chatResponseSchema = z.object({
  answer: z.string(), sources: z.array(sourceSchema).default([]),
  tool_events: z.array(toolEventSchema).default([]), conversation_id: z.string(),
});
export const healthSchema = z.object({
  status: z.string(), mode: z.string(), capabilities: z.record(z.string(), z.unknown()),
});
export type Course = z.infer<typeof courseSchema>;
export type Lecture = z.infer<typeof lectureSchema>;
export type Source = z.infer<typeof sourceSchema>;
export type Evidence = z.infer<typeof evidenceSchema>;
export type ToolEvent = z.infer<typeof toolEventSchema>;
export type Message = z.infer<typeof messageSchema>;
export type ChatResponse = z.infer<typeof chatResponseSchema>;
export type Health = z.infer<typeof healthSchema>;
export interface ChatRequest {
  course_id: string;
  lecture_id?: string | null;
  conversation_id: string;
  message: string;
}
export interface UploadRequest { title: string; file: File; lecture_id?: string }
export interface ApiClient {
  getHealth(signal?: AbortSignal): Promise<Health>;
  listCourses(signal?: AbortSignal): Promise<Course[]>;
  listLectures(courseId: string, signal?: AbortSignal): Promise<Lecture[]>;
  uploadLecture(courseId: string, input: UploadRequest, signal?: AbortSignal): Promise<Lecture>;
  chat(input: ChatRequest, signal?: AbortSignal): Promise<ChatResponse>;
  getHistory(courseId: string, conversationId: string, signal?: AbortSignal): Promise<Message[]>;
  sourceUrl(sourceId: string, page?: number): string | null;
}