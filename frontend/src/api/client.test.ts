import { afterEach, describe, expect, it, vi } from 'vitest';
import { createLiveClient } from './liveClient';
import { errorMessage } from './errors';

const lecture = { id: 'introduction', course_id: 'generative-ai', title: 'Introduction',
  filename: '00-Intro.pdf', source_id: 'intro-source', state: 'available', error: null };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

describe('live-only client selection', () => {
  afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); });

  it('uses the real backend by default', async () => {
    vi.stubEnv('VITE_WORKSHOP_API_MODE', '');
    vi.resetModules();
    const { api } = await import('./index');
    const { liveClient } = await import('./liveClient');
    expect(api).toBe(liveClient);
  });

  it('cannot switch back to mock data through a legacy environment flag', async () => {
    vi.stubEnv('VITE_WORKSHOP_API_MODE', 'mock');
    vi.resetModules();
    const { api } = await import('./index');
    const { liveClient } = await import('./liveClient');
    expect(api).toBe(liveClient);
  });
});

describe('live API contract', () => {
  it('unwraps catalog, lecture, history and health responses', async () => {
    const fetcher = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(json({ courses: [{ id: 'generative-ai', name: 'Generative AI' }] }))
      .mockResolvedValueOnce(json({ lectures: [lecture] }))
      .mockResolvedValueOnce(json({ messages: [{ role: 'user', content: 'Hello', sources: [], tool_events: [] }] }))
      .mockResolvedValueOnce(json({ status: 'ok', mode: 'student', capabilities: { chat: false } }));
    const client = createLiveClient('/api', fetcher);
    expect(await client.listCourses()).toHaveLength(1);
    expect(await client.listLectures('generative-ai')).toEqual([lecture]);
    expect(await client.getHistory('generative-ai', 'session-1')).toHaveLength(1);
    expect(await client.getHealth()).toMatchObject({ mode: 'student' });
    expect(fetcher.mock.calls[2][0]).toBe('/api/courses/generative-ai/conversations/session-1');
  });

  it('uploads title and file without a fabricated content-type or indexing success', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(json({ lecture }));
    const client = createLiveClient('/api', fetcher);
    const file = new File(['actual text'], 'notes.txt', { type: 'text/plain' });
    expect(await client.uploadLecture('generative-ai', { title: 'Notes', file })).toEqual(lecture);
    const options = fetcher.mock.calls[0][1];
    expect(options?.method).toBe('POST');
    expect(options?.headers).toBeUndefined();
    expect((options?.body as FormData).get('title')).toBe('Notes');
    expect((options?.body as FormData).get('file')).toBeInstanceOf(File);
    expect((options?.body as FormData).get('lecture_id')).toBeNull();
  });

  it('sends only the new message and scope, with no browser history or mode', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(json({ answer: 'Provided by backend', sources: [], tool_events: [], conversation_id: 'session-1' }));
    const input = { course_id: 'generative-ai', lecture_id: 'llms', conversation_id: 'session-1', message: 'Question' };
    await createLiveClient('/api', fetcher).chat(input);
    expect(fetcher.mock.calls[0][0]).toBe('/api/chat');
    expect(JSON.parse(fetcher.mock.calls[0][1]?.body as string)).toEqual(input);
  });

  it('reports sanitized backend errors and rejects malformed envelopes', async () => {
    const fetcher = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(json({ error: { code: 'unfinished_exercise', message: 'Complete exercise 3.' } }, 409))
      .mockResolvedValueOnce(json([lecture]));
    const client = createLiveClient('/api', fetcher);
    await expect(client.chat({ course_id: 'generative-ai', conversation_id: 'new', message: 'Hello' })).rejects.toMatchObject({ code: 'unfinished_exercise', status: 409 });
    await expect(client.listLectures('generative-ai')).rejects.toMatchObject({ code: 'invalid_response' });
  });

  it('uses server source IDs, encodes URLs and rejects filesystem paths', () => {
    const client = createLiveClient('/api');
    expect(client.sourceUrl('source id', 3)).toBe('/api/sources/source%20id#page=3');
    expect(client.sourceUrl('../docs/00-Intro.pdf')).toBeNull();
    expect(client.sourceUrl('C:\\private.pdf')).toBeNull();
    expect(client.sourceUrl('..')).toBeNull();
  });

  it('retains health status and capabilities when a degraded backend returns 503', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(json({ status: 'degraded', mode: 'student', capabilities: { chat: false } }, 503));
    await expect(createLiveClient('/api', fetcher).getHealth()).resolves.toMatchObject({ status: 'degraded', mode: 'student' });
  });

  it('does not render credentials from an error response', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(json({ error: { code: 'provider_unavailable', message: 'Denied sk-test-secret Bearer private-token' } }, 502));
    try { await createLiveClient('/api', fetcher).listCourses(); }
    catch (error) { expect(errorMessage(error)).not.toMatch(/sk-test|private-token/); }
  });
});
