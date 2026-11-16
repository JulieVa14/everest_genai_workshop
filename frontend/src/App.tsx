import { useEffect, useRef, useState } from 'react';
import {
  Badge, Button, Divider, Drawer, DrawerBody, DrawerHeader, DrawerHeaderTitle,
  Field, FluentProvider, Input, Link, MessageBar, MessageBarBody, Select,
  Skeleton, SkeletonItem, Spinner, Subtitle1, Tab, TabList, Textarea, Toolbar, Tooltip,
  useRestoreFocusSource, useRestoreFocusTarget,
} from '@fluentui/react-components';
import { BookOpen, FileText, Library, Menu, MessageSquare, Moon, Plus, RefreshCw, Send, Sun, Upload, X } from 'lucide-react';
import { api } from './api';
import { Answer } from './Answer';
import { useCompanion } from './useCompanion';
import { darkTheme, lightTheme } from './theme';

function ErrorNotice({ message, retry }: { message: string; retry?: () => void }) {
  return <MessageBar intent="error"><MessageBarBody>{message}
    {retry && <Button size="small" icon={<RefreshCw size={14} />} onClick={retry}>Reconnect</Button>}
  </MessageBarBody></MessageBar>;
}

function LoadingRows({ label }: { label: string }) {
  return <Skeleton aria-label={label} className="loading-rows">
    {[0, 1, 2].map(index => <SkeletonItem key={index} size={24} />)}
  </Skeleton>;
}

export default function App() {
  const companion = useCompanion();
  const drawerFocusSource = useRestoreFocusSource();
  const drawerFocusTarget = useRestoreFocusTarget();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [view, setView] = useState('conversation');
  const [draft, setDraft] = useState('');
  const [title, setTitle] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [uploadFor, setUploadFor] = useState('');
  const [search, setSearch] = useState('');
  const fileInput = useRef<HTMLInputElement>(null);
  const endOfMessages = useRef<HTMLDivElement>(null);
  const [dark, setDark] = useState(() => {
    try {
      const saved = localStorage.getItem('course-companion:theme');
      return saved ? saved === 'dark' : !!window.matchMedia?.('(prefers-color-scheme: dark)').matches;
    } catch { return false; }
  });
  useEffect(() => {
    const preference = window.matchMedia?.('(prefers-color-scheme: dark)');
    const update = (event: MediaQueryListEvent) => {
      try { if (!localStorage.getItem('course-companion:theme')) setDark(event.matches); } catch { setDark(event.matches); }
    };
    preference?.addEventListener('change', update);
    return () => preference?.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    endOfMessages.current?.scrollIntoView?.({ block: 'end', behavior: 'instant' });
  }, [companion.messages.length, companion.sending]);
  useEffect(() => { setDraft(''); setTitle(''); setFile(null); setUploadFor(''); setSearch(''); }, [companion.courseId, companion.sessionId]);
  const selectedCourse = companion.courses.find(course => course.id === companion.courseId);
  const selectedLecture = companion.lectures.find(lecture => lecture.id === companion.lectureId);
  const filteredLectures = companion.lectures.filter(lecture => (!companion.lectureId || lecture.id === companion.lectureId)
    && `${lecture.title} ${lecture.filename}`.toLowerCase().includes(search.toLowerCase()));
  const readyCount = companion.lectures.filter(lecture => lecture.state === 'ready').length;
  const busy = companion.sending || companion.uploading;

  async function uploadChosen(chosen: File | null) {
    if (await companion.upload(chosen, title, uploadFor || undefined)) {
      setTitle(''); setFile(null); setUploadFor('');
      if (fileInput.current) fileInput.current.value = '';
    }
  }

  function toggleTheme() {
    setDark(current => !current);
    try { localStorage.setItem('course-companion:theme', dark ? 'light' : 'dark'); } catch { return; }
  }

  const sidebar = <>
    <Field label="Course"><Select value={companion.courseId} disabled={companion.catalogLoading || companion.courses.length === 0}
      onChange={event => { companion.changeCourse(event.target.value); setDrawerOpen(false); }}>
      {companion.courses.length === 0 && <option value="generative-ai">Generative AI</option>}
      {companion.courses.map(course => <option key={course.id} value={course.id}>{course.name}</option>)}
    </Select></Field>
    {companion.catalogLoading ? <LoadingRows label="Loading courses" /> : companion.catalogError
      ? <ErrorNotice message={companion.catalogError} retry={companion.reconnect} /> : companion.courses.length === 0
        ? <div className="small-empty"><Library size={32} /><p>No courses available.</p><Button icon={<RefreshCw size={16} />} onClick={companion.reconnect}>Refresh catalog</Button></div> : null}
    <Divider />
    <div className="section-label"><Library size={16} aria-hidden="true" />Lectures <span>{companion.lectures.length}</span></div>
    {companion.lecturesLoading ? <LoadingRows label="Loading lectures" /> : companion.lectureError
      ? <ErrorNotice message={companion.lectureError} retry={companion.reconnect} /> : <TabList vertical size="small" className="lecture-tabs"
        selectedValue={companion.lectureId} onTabSelect={(_event, data) => {
          companion.setLectureId(String(data.value)); setDrawerOpen(false);
        }}>
        <Tab value="" icon={<Library size={17} />}>All lectures</Tab>
        {companion.lectures.map(lecture => <Tab key={lecture.id} value={lecture.id} icon={<FileText size={17} />}>
          {lecture.title}
        </Tab>)}
      </TabList>}
    <Divider />
    <div className="index-count"><span>{readyCount} ready</span><span>{companion.lectures.length - readyCount} not indexed</span></div>
    <Button icon={<Upload size={16} />} onClick={() => { setView('documents'); setDrawerOpen(false); }}>Upload document</Button>
    <div className="sidebar-bottom"><BookOpen size={18} aria-hidden="true" /><span>Generative AI workshop</span></div>
  </>;

  return <FluentProvider theme={dark ? darkTheme : lightTheme} className={`app ${dark ? 'dark' : ''}`}>
    <header className="app-header"><Toolbar aria-label="Workspace actions">
      <Tooltip content="Open lectures" relationship="label"><Button className="mobile-menu" aria-label="Open lectures"
        {...drawerFocusTarget} appearance="subtle" icon={<Menu size={20} />} onClick={() => setDrawerOpen(true)} /></Tooltip>
      <BookOpen className="brand-icon" size={25} aria-hidden="true" /><Subtitle1>Course Companion</Subtitle1>
      <div className="header-status"><Badge appearance="tint" color={companion.health?.mode === 'preview' ? 'warning' : 'brand'}>
        {companion.health ? `${companion.health.mode} · ${companion.health.status}` : 'Connecting'}
      </Badge></div>
      <Tooltip content="Reconnect and restore history" relationship="label"><Button aria-label="Reconnect and restore history" appearance="subtle"
        icon={<RefreshCw size={18} />} onClick={companion.reconnect} /></Tooltip>
      <Tooltip content={dark ? 'Light theme' : 'Dark theme'} relationship="label"><Button aria-label={dark ? 'Light theme' : 'Dark theme'}
        appearance="subtle" icon={dark ? <Sun size={18} /> : <Moon size={18} />} onClick={toggleTheme} /></Tooltip>
    </Toolbar></header>
    <div className="workspace">
      <aside className="desktop-sidebar" aria-label="Course and lecture navigation">{sidebar}</aside>
      <Drawer {...drawerFocusSource} type="overlay" position="start" open={drawerOpen} onOpenChange={(_event, data) => setDrawerOpen(data.open)}>
        <DrawerHeader><DrawerHeaderTitle action={<Button appearance="subtle" aria-label="Close lectures" icon={<X size={20} />} onClick={() => setDrawerOpen(false)} />}>
          Lectures</DrawerHeaderTitle></DrawerHeader>
        <DrawerBody className="drawer-navigation">{sidebar}</DrawerBody>
      </Drawer>
      <main className="main">
        <section className="course-heading"><div><span className="muted">Course workspace</span>
          <h1>{selectedCourse?.name || 'Generative AI'}</h1>
          <div className="scope"><FileText size={14} aria-hidden="true" />{selectedLecture?.title || 'All lectures'}<span className="scope-separator" />
            {readyCount}/{companion.lectures.length} indexed</div>
        </div><Button icon={<Plus size={17} />} onClick={companion.newConversation} disabled={companion.catalogLoading}>New conversation</Button></section>
        {companion.health?.mode === 'preview' && <MessageBar intent="warning"><MessageBarBody>
          Preview · Documents are available. Indexing and model responses are not connected.
        </MessageBarBody></MessageBar>}
        <TabList selectedValue={view} onTabSelect={(_event, data) => setView(String(data.value))} aria-label="Workspace view">
          <Tab value="conversation" icon={<MessageSquare size={17} />}>Conversation</Tab>
          <Tab value="documents" icon={<FileText size={17} />}>Documents ({companion.lectures.length})</Tab>
        </TabList>
        {view === 'conversation' ? <section className="conversation" aria-label="Conversation">
          <div className="message-scroll" aria-busy={companion.historyLoading || companion.sending}>
            {companion.historyLoading ? <LoadingRows label="Restoring conversation" /> : companion.historyError
              ? <ErrorNotice message={companion.historyError} retry={companion.reconnect} />
              : companion.messages.length === 0 ? <div className="empty-conversation">
                <MessageSquare size={64} strokeWidth={1.2} aria-hidden="true" /><h2>No messages yet</h2>
                <span className="muted">{selectedLecture?.title || 'All lectures'}</span>
                <Button appearance="subtle" icon={<FileText size={16} />} onClick={() => setView('documents')}>Open documents</Button>
              </div> : companion.messages.map((message, index) => <Answer key={`${companion.sessionId}-${index}`} message={message} />)}
            {companion.sending && <div className="pending-message" role="status"><Spinner size="tiny" />Waiting for course companion...</div>}
            <div ref={endOfMessages} />
          </div>
          <div className="composer-region">
            {companion.chatError && <ErrorNotice message={companion.chatError} retry={companion.reconnect} />}
            <form className="composer" onSubmit={event => {
              event.preventDefault(); void companion.send(draft).then(sent => { if (sent) setDraft(''); });
            }}>
              <Field label="Your question" validationState={draft.length > 4000 ? 'error' : 'none'}
                validationMessage={draft.length > 4000 ? 'Keep your question within 4,000 characters.' : undefined}>
                <Textarea value={draft} placeholder="Ask a question about this course..." resize="vertical"
                  disabled={companion.sending} onChange={(_event, data) => setDraft(data.value)} />
              </Field>
              <div className="composer-actions"><span className="muted">{selectedLecture?.title || 'All lectures'} · {draft.length}/4000</span>
                <Button type="submit" appearance="primary" icon={<Send size={16} />}
                  disabled={!draft.trim() || draft.length > 4000 || companion.sending || companion.historyLoading || !!companion.historyError || companion.catalogLoading || !selectedCourse}>
                  {companion.sending ? 'Sending' : 'Send question'}</Button>
              </div>
            </form>
          </div>
        </section> : <section className="documents" aria-label="Document catalog">
          <div className="catalog-toolbar"><h2><Library size={19} aria-hidden="true" />Document catalog</h2>
            <Input aria-label="Filter documents" value={search} placeholder="Filter documents" onChange={(_event, data) => setSearch(data.value)} />
          </div>
          {companion.lectureError && <ErrorNotice message={companion.lectureError} retry={companion.reconnect} />}
          {companion.lecturesLoading ? <LoadingRows label="Loading document catalog" /> : filteredLectures.length === 0
            ? <div className="small-empty"><FileText size={48} aria-hidden="true" /><p>No matching documents.</p>
              <Button onClick={() => { setSearch(''); companion.setLectureId(''); }}>Clear filters</Button></div>
            : <ul className="catalog-list">{filteredLectures.map(lecture => {
              const href = api.sourceUrl(lecture.source_id);
              return <li key={lecture.id}>
                <FileText size={23} className="document-icon" aria-hidden="true" />
                <div className="document-info"><strong>{lecture.title}</strong><span className="muted">{lecture.filename}</span>
                  {lecture.error && <span className="document-error">{lecture.error}</span>}</div>
                <Badge appearance="tint" color={lecture.state === 'ready' ? 'success' : lecture.state === 'error' ? 'danger' : 'informative'}>
                  {lecture.state === 'ready' ? 'Indexed' : lecture.state === 'indexing' ? 'Indexing' : lecture.state === 'error' ? 'Error' : 'Available'}</Badge>
                <div className="document-actions">{href && <Link href={href} target="_blank" rel="noopener noreferrer">Open PDF</Link>}
                  {lecture.state !== 'ready' && <Tooltip content="Choose the original file to index this lecture" relationship="description">
                    <Button size="small" icon={<Upload size={14} />} disabled={companion.uploading || lecture.state === 'indexing'}
                      onClick={() => { setTitle(lecture.title); setUploadFor(lecture.id); fileInput.current?.click(); }}>Index</Button>
                  </Tooltip>}
                </div>
              </li>;
            })}</ul>}
          <Divider />
          <form className="upload-form" onSubmit={event => {
            event.preventDefault(); void uploadChosen(file);
          }}>
            <h2><Upload size={19} aria-hidden="true" />Upload & index</h2>
            {companion.uploadError && <ErrorNotice message={companion.uploadError} />}
            <Field label="Lecture title"><Input value={title} maxLength={200} disabled={companion.uploading}
              onChange={(_event, data) => { setTitle(data.value); setUploadFor(''); }} /></Field>
            <Field label="Document" validationState={!file ? 'warning' : 'none'} validationMessage={!file ? 'Choose a PDF or .txt file, up to 10 MB.' : undefined}>
              <input ref={fileInput} aria-label="Document file" type="file" accept=".pdf,.txt,application/pdf,text/plain"
                disabled={companion.uploading} onChange={event => {
                  const chosen = event.target.files?.[0] || null; setFile(chosen);
                  if (chosen && uploadFor) { void uploadChosen(chosen); return; }
                  if (!title && chosen) setTitle(chosen.name.replace(/\.(pdf|txt)$/i, ''));
                }} />
            </Field>
            <div className="upload-actions">{file && <span className="muted">{file.name} · {(file.size / 1024 / 1024).toFixed(2)} MB</span>}
              <Button type="submit" appearance="primary" icon={companion.uploading ? <Spinner size="tiny" /> : <Upload size={16} />}
                disabled={busy || !file || !title.trim() || companion.catalogLoading || !selectedCourse}>
                {companion.uploading ? 'Indexing document' : 'Upload & index'}</Button>
            </div>
          </form>
        </section>}
      </main>
    </div>
  </FluentProvider>;
}