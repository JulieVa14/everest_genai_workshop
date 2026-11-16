const key = (courseId: string) => `course-companion:conversation:${courseId}`;
const memory = new Map<string, string>();
const validId = /^[a-zA-Z0-9_-]{1,80}$/;

export function conversationId(courseId: string, fresh = false): string {
  let saved: string | null = memory.get(courseId) || null;
  try { saved = localStorage.getItem(key(courseId)) || saved; } catch { saved = memory.get(courseId) || null; }
  if (!fresh && saved && validId.test(saved)) { memory.set(courseId, saved); return saved; }
  const id = crypto.randomUUID();
  memory.set(courseId, id);
  try { localStorage.setItem(key(courseId), id); } catch { return id; }
  return id;
}

export function saveConversationId(courseId: string, id: string): void {
  if (!validId.test(id)) throw new Error('Invalid conversation ID returned by backend');
  memory.set(courseId, id);
  try { localStorage.setItem(key(courseId), id); } catch { return; }
}