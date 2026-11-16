import { useEffect, useRef, useState } from 'react';
import { api } from './api';
import { ApiError, errorMessage } from './api/errors';
import type { Course, Health, Lecture, Message } from './api/types';
import { conversationId, saveConversationId } from './conversations';

export function validateUpload(file: File | null, title: string): string | null {
  if (!title.trim()) return 'Enter a lecture title.';
  if (!file) return 'Choose a PDF or text file.';
  if (!/\.(pdf|txt)$/i.test(file.name)) return 'Choose a PDF or .txt file.';
  if (file.size === 0) return 'The file is empty.';
  if (file.size > 10 * 1024 * 1024) return 'The file exceeds the 10 MB limit.';
  return null;
}

export function useCompanion() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [courseId, setCourseId] = useState('generative-ai');
  const [lectureId, setLectureId] = useState('');
  const [lectures, setLectures] = useState<Lecture[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState(() => conversationId('generative-ai'));
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [lecturesLoading, setLecturesLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [catalogError, setCatalogError] = useState('');
  const [lectureError, setLectureError] = useState('');
  const [historyError, setHistoryError] = useState('');
  const [chatError, setChatError] = useState('');
  const [uploadError, setUploadError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [sending, setSending] = useState(false);
  const [revision, setRevision] = useState(0);
  const activeCourse = useRef(courseId);
  const chatOperation = useRef<AbortController | null>(null);
  const uploadOperation = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setCatalogLoading(true); setCatalogError('');
    void Promise.all([api.listCourses(controller.signal), api.getHealth(controller.signal)])
      .then(([list, status]) => {
        if (controller.signal.aborted) return;
        setCourses(list); setHealth(status);
        if (list.length && !list.some(item => item.id === activeCourse.current)) {
          const next = list[0].id;
          activeCourse.current = next; setCourseId(next); setSessionId(conversationId(next));
        }
      }).catch(error => { if (!controller.signal.aborted) setCatalogError(errorMessage(error)); })
      .finally(() => { if (!controller.signal.aborted) setCatalogLoading(false); });
    return () => controller.abort();
  }, [revision]);

  useEffect(() => {
    const controller = new AbortController();
    setLectures([]); setLecturesLoading(true); setLectureError('');
    void api.listLectures(courseId, controller.signal).then(list => {
      if (!controller.signal.aborted) {
        setLectures(list);
        setLectureId(current => list.some(item => item.id === current) ? current : '');
      }
    }).catch(error => { if (!controller.signal.aborted) setLectureError(errorMessage(error)); })
      .finally(() => { if (!controller.signal.aborted) setLecturesLoading(false); });
    return () => controller.abort();
  }, [courseId, revision]);

  useEffect(() => {
    const controller = new AbortController();
    setMessages([]); setHistoryError(''); setHistoryLoading(true);
    void api.getHistory(courseId, sessionId, controller.signal).then(history => {
      if (!controller.signal.aborted) setMessages(history);
    }).catch(error => {
      if (!controller.signal.aborted && !(error instanceof ApiError && error.status === 404)) setHistoryError(errorMessage(error));
    }).finally(() => { if (!controller.signal.aborted) setHistoryLoading(false); });
    return () => controller.abort();
  }, [courseId, sessionId, revision]);

  useEffect(() => {
    const reconnect = () => {
      chatOperation.current?.abort(); uploadOperation.current?.abort();
      setSending(false); setUploading(false); setChatError(''); setUploadError('');
      setRevision(value => value + 1);
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === `course-companion:conversation:${activeCourse.current}`) {
        chatOperation.current?.abort(); setSending(false); setChatError('');
        setSessionId(conversationId(activeCourse.current)); reconnect();
      }
    };
    window.addEventListener('online', reconnect);
    window.addEventListener('storage', onStorage);
    return () => {
      window.removeEventListener('online', reconnect); window.removeEventListener('storage', onStorage);
      chatOperation.current?.abort(); uploadOperation.current?.abort();
    };
  }, []);

  function changeCourse(id: string) {
    chatOperation.current?.abort(); uploadOperation.current?.abort();
    activeCourse.current = id;
    setCourseId(id); setSessionId(conversationId(id)); setLectureId(''); setMessages([]); setHistoryLoading(true);
    setChatError(''); setUploadError(''); setSending(false); setUploading(false);
  }

  function newConversation() {
    chatOperation.current?.abort(); setSending(false); setChatError(''); setMessages([]);
    setSessionId(conversationId(courseId, true)); setHistoryLoading(true);
  }

  function reconnect() {
    chatOperation.current?.abort(); uploadOperation.current?.abort();
    setSending(false); setUploading(false); setChatError(''); setUploadError('');
    setRevision(value => value + 1);
  }

  async function send(message: string): Promise<boolean> {
    if (sending || (chatOperation.current && !chatOperation.current.signal.aborted) || historyLoading || historyError || !message.trim() || message.trim().length > 4000) return false;
    const controller = new AbortController();
    chatOperation.current = controller;
    setSending(true); setChatError('');
    try {
      const response = await api.chat({ course_id: courseId, lecture_id: lectureId || null,
        conversation_id: sessionId, message: message.trim() }, controller.signal);
      if (controller.signal.aborted || activeCourse.current !== courseId) return false;
      if (response.conversation_id !== sessionId) throw new ApiError('The backend returned a different conversation. Reconnect before sending again.', 409, 'conversation_mismatch');
      saveConversationId(courseId, response.conversation_id);
      setMessages(current => [...current,
        { role: 'user', content: message.trim(), sources: [], tool_events: [] },
        { role: 'assistant', content: response.answer, sources: response.sources, tool_events: response.tool_events },
      ]);
      return true;
    } catch (error) {
      if (!controller.signal.aborted) setChatError(errorMessage(error));
      return false;
    } finally {
      if (chatOperation.current === controller) chatOperation.current = null;
      if (!controller.signal.aborted) setSending(false);
    }
  }

  async function upload(file: File | null, title: string, existingLectureId?: string): Promise<boolean> {
    const validation = validateUpload(file, title);
    if (validation || !file) { setUploadError(validation || 'Choose a file.'); return false; }
    if (uploading || (uploadOperation.current && !uploadOperation.current.signal.aborted)) return false;
    const controller = new AbortController();
    uploadOperation.current = controller;
    setUploading(true); setUploadError('');
    try {
      const lecture = await api.uploadLecture(courseId, { title: title.trim(), file, lecture_id: existingLectureId }, controller.signal);
      if (controller.signal.aborted || activeCourse.current !== courseId) return false;
      if (lecture.course_id !== courseId) throw new ApiError('Uploaded lecture belongs to a different course. Reconnect.', 409, 'scope_mismatch');
      setLectures(current => [...current.filter(item => item.id !== lecture.id), lecture]);
      if (lecture.state !== 'ready') {
        setUploadError(lecture.error || 'The backend has not confirmed indexing. Refresh the catalog to check its state.');
        return false;
      }
      setLectureId(lecture.id);
      return true;
    } catch (error) {
      if (!controller.signal.aborted) setUploadError(errorMessage(error));
      return false;
    } finally {
      if (uploadOperation.current === controller) uploadOperation.current = null;
      if (!controller.signal.aborted) setUploading(false);
    }
  }

  return { courses, health, courseId, lectureId, setLectureId, lectures, messages, sessionId,
    catalogLoading, lecturesLoading, historyLoading, catalogError, lectureError, historyError,
    chatError, uploadError, uploading, sending, changeCourse, newConversation, reconnect, send, upload };
}