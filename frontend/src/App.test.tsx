import { act, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { FluentProvider } from '@fluentui/react-components';
import App from './App';
import { Answer } from './Answer';
import { api } from './api';
import { ApiError } from './api/errors';
import type { ChatResponse, Lecture, Message } from './api/types';
import { conversationId } from './conversations';
import { useCompanion, validateUpload } from './useCompanion';
import { lightTheme } from './theme';

vi.mock('./api', () => ({ api: {
  getHealth: vi.fn(), listCourses: vi.fn(), listLectures: vi.fn(), uploadLecture: vi.fn(),
  chat: vi.fn(), getHistory: vi.fn(), sourceUrl: vi.fn(),
} }));

const lecture: Lecture = { id: 'llms', course_id: 'generative-ai', title: 'Large Language Models',
  filename: '01-LLMs.pdf', source_id: 'llm-source', state: 'available', error: null };
const source = { chunk_id: 'chunk-test', lecture_id: 'llms', filename: '01-LLMs.pdf', page: 2, source_id: 'llm-source' };
const history: Message[] = [{ role: 'user', content: 'Stored test question', sources: [], tool_events: [] }];

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  vi.mocked(api.getHealth).mockResolvedValue({ status: 'preview', mode: 'preview', capabilities: { chat: false, indexing: false } });
  vi.mocked(api.listCourses).mockResolvedValue([{ id: 'generative-ai', name: 'Generative AI' }, { id: 'other-course', name: 'Other course' }]);
  vi.mocked(api.listLectures).mockImplementation(async id => [{ ...lecture, course_id: id }]);
  vi.mocked(api.getHistory).mockResolvedValue([]);
  vi.mocked(api.sourceUrl).mockImplementation((id, page) => id === 'llm-source' ? `/api/sources/${id}${page ? `#page=${page}` : ''}` : null);
  vi.mocked(api.chat).mockImplementation(async input => ({ answer: 'Backend test fixture', sources: [source], tool_events: [], conversation_id: input.conversation_id }));
  vi.mocked(api.uploadLecture).mockResolvedValue({ ...lecture, state: 'ready' });
});

describe('course conversation lifecycle', () => {
  it('restores the same course-bound ID after remount without storing messages', async () => {
    vi.mocked(api.getHistory).mockResolvedValue(history);
    const first = renderHook(useCompanion);
    await waitFor(() => expect(first.result.current.historyLoading).toBe(false));
    const id = first.result.current.sessionId;
    expect(first.result.current.messages).toEqual(history);
    first.unmount();
    const second = renderHook(useCompanion);
    await waitFor(() => expect(second.result.current.historyLoading).toBe(false));
    expect(second.result.current.sessionId).toBe(id);
    expect(api.getHistory).toHaveBeenLastCalledWith('generative-ai', id, expect.any(AbortSignal));
    expect(localStorage.getItem('course-companion:conversation:generative-ai')).toBe(id);
    expect(localStorage.length).toBe(1);
    expect(localStorage.key(0)).toBe('course-companion:conversation:generative-ai');
  });

  it('keeps separate course IDs, scopes new messages and preserves the first course', async () => {
    const { result } = renderHook(useCompanion);
    await waitFor(() => expect(result.current.historyLoading).toBe(false));
    const original = result.current.sessionId;
    act(() => { result.current.changeCourse('other-course'); });
    await waitFor(() => expect(result.current.historyLoading).toBe(false));
    const other = result.current.sessionId;
    expect(other).not.toBe(original);
    act(() => result.current.setLectureId('llms'));
    await act(async () => { expect(await result.current.send('Next question')).toBe(true); });
    expect(api.chat).toHaveBeenLastCalledWith({ course_id: 'other-course', lecture_id: 'llms', conversation_id: other, message: 'Next question' }, expect.any(AbortSignal));
    act(() => result.current.changeCourse('generative-ai'));
    expect(result.current.sessionId).toBe(original);
  });

  it('creates a fresh UUID and resets history without deleting other course IDs', async () => {
    const other = conversationId('other-course', true);
    vi.mocked(api.getHistory).mockResolvedValueOnce(history).mockResolvedValue([]);
    const { result } = renderHook(useCompanion);
    await waitFor(() => expect(result.current.messages).toEqual(history));
    const original = result.current.sessionId;
    act(() => result.current.newConversation());
    await waitFor(() => expect(result.current.historyLoading).toBe(false));
    expect(result.current.sessionId).not.toBe(original);
    expect(result.current.messages).toEqual([]);
    expect(conversationId('other-course')).toBe(other);
  });

  it('restores history on reconnect and browser online without resending a message', async () => {
    const { result } = renderHook(useCompanion);
    await waitFor(() => expect(result.current.historyLoading).toBe(false));
    vi.mocked(api.getHistory).mockResolvedValue(history);
    act(() => result.current.reconnect());
    await waitFor(() => expect(result.current.messages).toEqual(history));
    const calls = vi.mocked(api.getHistory).mock.calls.length;
    act(() => window.dispatchEvent(new Event('online')));
    await waitFor(() => expect(vi.mocked(api.getHistory).mock.calls.length).toBeGreaterThan(calls));
    expect(api.chat).not.toHaveBeenCalled();
  });

  it('discards late history from a previous course even if the transport ignores abort', async () => {
    let resolveHistory!: (messages: Message[]) => void;
    vi.mocked(api.getHistory).mockImplementationOnce(() => new Promise(resolve => { resolveHistory = resolve; }));
    const { result } = renderHook(useCompanion);
    act(() => result.current.changeCourse('other-course'));
    await waitFor(() => expect(result.current.historyLoading).toBe(false));
    await act(async () => resolveHistory(history));
    expect(result.current.messages).toEqual([]);
    expect(result.current.courseId).toBe('other-course');
  });

  it('discards late chat from a previous course and clears its pending state', async () => {
    let resolveChat!: (response: ChatResponse) => void;
    vi.mocked(api.chat).mockImplementationOnce(() => new Promise(resolve => { resolveChat = resolve; }));
    const { result } = renderHook(useCompanion);
    await waitFor(() => expect(result.current.historyLoading).toBe(false));
    const original = result.current.sessionId;
    let pending!: Promise<boolean>;
    act(() => { pending = result.current.send('Question'); });
    expect(result.current.sending).toBe(true);
    act(() => result.current.changeCourse('other-course'));
    await act(async () => { resolveChat({ answer: 'Stale fixture', sources: [], tool_events: [], conversation_id: original }); await pending; });
    expect(result.current.sending).toBe(false);
    expect(result.current.messages).toEqual([]);
  });

  it('treats a missing fresh history as empty but surfaces other history failures', async () => {
    vi.mocked(api.getHistory).mockRejectedValueOnce(new ApiError('No conversation yet', 404, 'not_found'));
    const { result } = renderHook(useCompanion);
    await waitFor(() => expect(result.current.historyLoading).toBe(false));
    expect(result.current.historyError).toBe('');
    vi.mocked(api.getHistory).mockRejectedValue(new ApiError('History unavailable', 502));
    act(() => result.current.reconnect());
    await waitFor(() => expect(result.current.historyError).toBe('History unavailable'));
    await act(async () => { expect(await result.current.send('Question')).toBe(false); });
    expect(api.chat).not.toHaveBeenCalled();
  });

  it('does not mark an unconfirmed upload indexed', async () => {
    vi.mocked(api.uploadLecture).mockResolvedValue({ ...lecture, state: 'available' });
    const { result } = renderHook(useCompanion);
    await waitFor(() => expect(result.current.lecturesLoading).toBe(false));
    await act(async () => {
      expect(await result.current.upload(new File(['notes'], 'notes.txt'), 'Notes')).toBe(false);
    });
    expect(result.current.uploadError).toContain('not confirmed indexing');
    expect(result.current.lectures[0].state).toBe('available');
  });
});

describe('usable workspace', () => {
  it('has an honest empty conversation and opens real source documents', async () => {
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText('No messages yet')).toBeVisible();
    expect(screen.getByText(/Indexing and model responses are not connected/)).toBeVisible();
    await user.click(screen.getByRole('tab', { name: 'Documents (1)' }));
    expect(screen.getByText('Available')).toBeVisible();
    expect(screen.getByRole('link', { name: 'Open PDF' })).toHaveAttribute('href', '/api/sources/llm-source');
    expect(screen.queryByLabelText('Course companion answer')).not.toBeInTheDocument();
  });

  it('retains the draft after failed preview chat, exposes errors, and does not invent messages', async () => {
    vi.mocked(api.chat).mockRejectedValue(new ApiError('Preview only: model not connected', 503));
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('No messages yet');
    const input = screen.getByLabelText('Your question');
    await user.type(input, 'My question');
    await user.click(screen.getByRole('button', { name: 'Send question' }));
    expect(await screen.findByText('Preview only: model not connected')).toBeVisible();
    expect(input).toHaveValue('My question');
    expect(screen.queryByLabelText('Your message')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Send question' })).toBeEnabled();
  });

  it('covers pending chat and renders backend-provided answers and citation URLs', async () => {
    let resolveChat!: (response: ChatResponse) => void;
    vi.mocked(api.chat).mockImplementationOnce(() => new Promise(resolve => { resolveChat = resolve; }));
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('No messages yet');
    await user.type(screen.getByLabelText('Your question'), 'Question');
    await user.click(screen.getByRole('button', { name: 'Send question' }));
    expect(screen.getByRole('button', { name: 'Sending' })).toBeDisabled();
    const id = vi.mocked(api.chat).mock.calls[0][0].conversation_id;
    await act(async () => resolveChat({ answer: '**Backend fixture**', sources: [source], tool_events: [], conversation_id: id }));
    expect(await screen.findByText('Backend fixture')).toBeVisible();
    expect(screen.getByRole('link', { name: /01-LLMs.pdf/ })).toHaveAttribute('href', '/api/sources/llm-source#page=2');
    expect(screen.getByLabelText('Your question')).toHaveValue('');
  });

  it('filters the catalog by lecture and search text', async () => {
    vi.mocked(api.listLectures).mockResolvedValue([lecture, { ...lecture, id: 'ethics', title: 'Generative AI Ethics', filename: '05-GAI_ethics.pdf' }]);
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('No messages yet');
    await user.click(screen.getByRole('tab', { name: 'Large Language Models' }));
    await user.click(screen.getByRole('tab', { name: 'Documents (2)' }));
    expect(screen.getByText('01-LLMs.pdf')).toBeVisible();
    expect(screen.queryByText('05-GAI_ethics.pdf')).not.toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: 'Filter documents' }), 'missing');
    expect(screen.getByText('No matching documents.')).toBeVisible();
  });

  it('shows failed upload without changing the available catalog state', async () => {
    vi.mocked(api.uploadLecture).mockRejectedValue(new ApiError('Preview only: indexing unavailable', 503));
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('No messages yet');
    await user.click(screen.getByRole('tab', { name: 'Documents (1)' }));
    await user.type(screen.getByLabelText('Lecture title'), 'Notes');
    await user.upload(screen.getByLabelText('Document file'), new File(['notes'], 'notes.txt', { type: 'text/plain' }));
    await user.click(screen.getByRole('button', { name: 'Upload & index' }));
    expect(await screen.findByText('Preview only: indexing unavailable')).toBeVisible();
    expect(screen.getByText('Available')).toBeVisible();
    expect(screen.queryByText('Indexed')).not.toBeInTheDocument();
  });

  it('indexes a lecture as soon as its file is chosen from the Index action', async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('No messages yet');
    await user.click(screen.getByRole('tab', { name: 'Documents (1)' }));
    await user.click(screen.getByRole('button', { name: 'Index' }));
    const pdf = new File(['%PDF-1.4'], '01-LLMs.pdf', { type: 'application/pdf' });
    await user.upload(screen.getByLabelText('Document file'), pdf);
    await waitFor(() => expect(api.uploadLecture).toHaveBeenCalledWith('generative-ai',
      { title: 'Large Language Models', file: pdf, lecture_id: 'llms' }, expect.any(AbortSignal)));
    expect(await screen.findByText('Indexed')).toBeVisible();
  });

  it('makes loading, error, empty catalog states visible', async () => {
    vi.mocked(api.listCourses).mockImplementationOnce(() => new Promise(() => {}));
    const loading = render(<App />);
    expect(screen.getByLabelText('Loading courses')).toBeVisible();
    loading.unmount();
    vi.mocked(api.listCourses).mockRejectedValueOnce(new ApiError('Catalog unavailable', 503));
    const error = render(<App />);
    expect(await screen.findByText('Catalog unavailable')).toBeVisible();
    error.unmount();
    vi.mocked(api.listCourses).mockResolvedValue([]);
    render(<App />);
    expect(await screen.findByText('No courses available.')).toBeVisible();
  });

  it('opens and closes a focus-managed mobile drawer', async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('No messages yet');
    const trigger = screen.getByRole('button', { name: 'Open lectures', hidden: true });
    expect(JSON.parse(trigger.getAttribute('data-tabster') || '{}')).toHaveProperty('restorer');
    fireEvent.click(trigger);
    expect(await screen.findByRole('button', { name: 'Close lectures' })).toBeVisible();
    expect(JSON.parse(screen.getByRole('dialog').getAttribute('data-tabster') || '{}')).toHaveProperty('restorer');
    await user.click(screen.getByRole('button', { name: 'Close lectures' }));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Close lectures' })).not.toBeInTheDocument());
  });
});

describe('safe content and upload validation', () => {
  it('omits raw HTML and arbitrary markdown links but retains validated citations and tool evidence', () => {
    render(<FluentProvider theme={lightTheme}><Answer message={{ role: 'assistant',
      content: '<script>alert(1)</script>\n\n[Unsafe](javascript:alert(1)) **Safe text**', sources: [source],
      tool_events: [{ name: 'search_course_docs', arguments: { course_id: 'generative-ai', lecture_id: null }, evidence: [source] }],
    }} /></FluentProvider>);
    expect(document.querySelector('script')).toBeNull();
    expect(screen.getByText('Safe text')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Unsafe' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /01-LLMs.pdf/ })).toHaveLength(2);
    expect(screen.getByText('search_course_docs')).toBeInTheDocument();
  });

  it('rejects empty, unsupported and oversized uploads before network access', () => {
    expect(validateUpload(null, 'Notes')).toMatch(/Choose/);
    expect(validateUpload(new File(['text'], 'notes.txt'), '')).toMatch(/title/);
    expect(validateUpload(new File([], 'notes.pdf'), 'Notes')).toMatch(/empty/);
    expect(validateUpload(new File(['text'], 'notes.exe'), 'Notes')).toMatch(/PDF/);
    const large = new File(['text'], 'large.pdf');
    Object.defineProperty(large, 'size', { value: 10 * 1024 * 1024 + 1 });
    expect(validateUpload(large, 'Notes')).toMatch(/10 MB/);
    expect(validateUpload(new File(['text'], 'notes.txt'), 'Notes')).toBeNull();
  });
});