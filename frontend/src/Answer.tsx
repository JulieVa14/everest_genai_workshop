import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Link } from '@fluentui/react-components';
import { ExternalLink, Search } from 'lucide-react';
import { api } from './api';
import type { Message, Source } from './api/types';

function SourceLink({ source }: { source: Source }) {
  const url = api.sourceUrl(source.source_id, source.page);
  const label = `${source.filename} · p. ${source.page}`;
  return url ? <Link className="citation" href={url} target="_blank" rel="noopener noreferrer">
    <ExternalLink size={13} aria-hidden="true" />{label}</Link> : <span className="muted">Source unavailable: {label}</span>;
}

export function Answer({ message }: { message: Message }) {
  return <article className={`message ${message.role}`} aria-label={message.role === 'user' ? 'Your message' : 'Course companion answer'}>
    <div className="message-label">{message.role === 'user' ? 'You' : 'Course Companion'}</div>
    <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml
      allowedElements={['p', 'strong', 'em', 'ul', 'ol', 'li', 'code', 'pre', 'blockquote', 'h1', 'h2', 'h3', 'h4', 'hr', 'br', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'del', 'a']}
      components={{ a: ({ children }) => <span>{children}</span> }}>
      {message.content}
    </ReactMarkdown></div>
    {message.sources.length > 0 && <div className="sources" aria-label="Cited sources">
      {message.sources.map((source, index) => <SourceLink key={`${source.chunk_id}-${index}`} source={source} />)}
    </div>}
    {message.tool_events.length > 0 && <details className="tool-events">
      <summary><Search size={14} aria-hidden="true" />Tool activity · {message.tool_events.length} events</summary>
      {message.tool_events.map((event, index) => <div className="tool-event" key={`${event.name}-${index}`}>
        <strong>{event.name}</strong>
        {Object.entries(event.arguments).length > 0 && <dl>{Object.entries(event.arguments).map(([name, value]) =>
          <div key={name}><dt>{name}</dt><dd>{String(value ?? 'All')}</dd></div>)}</dl>}
        <span className="muted">{event.evidence.length} evidence references</span>
        <div className="sources">{event.evidence.map((source, evidenceIndex) =>
          <SourceLink key={`${source.chunk_id}-${evidenceIndex}`} source={source} />)}</div>
      </div>)}
    </details>}
  </article>;
}