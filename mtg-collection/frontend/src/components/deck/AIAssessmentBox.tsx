import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Caption1 } from '@fluentui/react-components';
import { DeckDetail } from '../../api';
import styles from './AIAssessmentBox.module.css';

interface Props {
  deck: DeckDetail;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

const STORAGE_KEY = 'ai-assessment-expanded';

export function AIAssessmentBox({ deck }: Props) {
  const [expanded, setExpanded] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) === 'true'; } catch { return false; }
  });

  const toggle = () => {
    const next = !expanded;
    setExpanded(next);
    try { localStorage.setItem(STORAGE_KEY, String(next)); } catch {}
  };

  if (!deck.ai_assessment) {
    return <Caption1 style={{ opacity: 0.5, display: 'block', marginTop: 12 }}>No AI assessment yet. Ask the MCP assistant to analyze this deck.</Caption1>;
  }

  return (
    <div style={{ marginTop: 12, padding: 12, borderRadius: 8, background: 'var(--colorNeutralBackground3, #f5f5f5)' }}>
      <div onClick={toggle} style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 12, color: 'var(--colorNeutralForeground3, #888)', transition: 'transform 0.2s', transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
        <Caption1 style={{ opacity: 0.6 }}>
          AI Assessment {deck.ai_assessment_updated_at && `· ${timeAgo(deck.ai_assessment_updated_at)}`}
        </Caption1>
      </div>
      {expanded && (
        <div className={styles.markdownContent} style={{ marginTop: 8 }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {deck.ai_assessment}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}
