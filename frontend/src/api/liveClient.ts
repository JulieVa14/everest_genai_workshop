import { z } from 'zod';
import { ApiError } from './errors';
import {
  chatResponseSchema, courseSchema, healthSchema, lectureSchema, messageSchema,
} from './types';
import type { ApiClient } from './types';

export function createLiveClient(baseUrl = '/api', fetcher: typeof fetch = fetch): ApiClient {
  const base = baseUrl.replace(/\/$/, '');
  const segment = (value: string) => encodeURIComponent(value);

  async function request<Output>(path: string, schema: z.ZodType<Output>, options: RequestInit = {}, acceptedStatuses: number[] = []): Promise<Output> {
    const signal = options.signal
      ? AbortSignal.any([options.signal, AbortSignal.timeout(120_000)])
      : AbortSignal.timeout(120_000);
    let response: Response;
    try {
      response = await fetcher(`${base}${path}`, { ...options, signal, credentials: 'omit' });
    } catch (error) {
      if (options.signal?.aborted) throw error;
      throw new ApiError('The local backend is unreachable or timed out. Start it, then reconnect.');
    }
    let body: unknown;
    try { body = await response.json(); }
    catch { throw new ApiError('The backend returned an unreadable response.', response.status, 'invalid_response'); }
    if (!response.ok && !acceptedStatuses.includes(response.status)) {
      const envelope = z.object({ error: z.object({ code: z.string(), message: z.string() }) }).safeParse(body);
      const detail = z.object({ detail: z.string() }).safeParse(body);
      throw new ApiError(envelope.success ? envelope.data.error.message : detail.success ? detail.data.detail
        : `Backend request failed (${response.status}). Check the backend configuration or exercise.`,
      response.status, envelope.success ? envelope.data.error.code : 'request_failed');
    }
    const parsed = schema.safeParse(body);
    if (!parsed.success) throw new ApiError('The backend response does not match the workshop API contract.', response.status, 'invalid_response');
    return parsed.data;
  }

  return {
    getHealth: signal => request('/health', healthSchema, { signal }, [503]),
    listCourses: async signal => (await request('/courses', z.object({ courses: z.array(courseSchema) }), { signal })).courses,
    listLectures: async (courseId, signal) => (await request(`/courses/${segment(courseId)}/lectures`,
      z.object({ lectures: z.array(lectureSchema) }), { signal })).lectures,
    uploadLecture: async (courseId, input, signal) => {
      const body = new FormData();
      body.append('title', input.title);
      body.append('file', input.file);
      if (input.lecture_id) body.append('lecture_id', input.lecture_id);
      return (await request(`/courses/${segment(courseId)}/lectures`, z.object({ lecture: lectureSchema }),
        { method: 'POST', body, signal })).lecture;
    },
    chat: (input, signal) => request('/chat', chatResponseSchema, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input), signal,
    }),
    getHistory: async (courseId, conversationId, signal) => (await request(
      `/courses/${segment(courseId)}/conversations/${segment(conversationId)}`,
      z.object({ messages: z.array(messageSchema) }), { signal })).messages,
    sourceUrl: (sourceId, page) => {
      if (!sourceId || /[\\/\x00-\x1f]/.test(sourceId) || sourceId === '.' || sourceId === '..') return null;
      return `${base}/sources/${segment(sourceId)}${page && Number.isInteger(page) && page > 0 ? `#page=${page}` : ''}`;
    },
  };
}

export const liveClient = createLiveClient(import.meta.env.VITE_API_BASE_URL || '/api');