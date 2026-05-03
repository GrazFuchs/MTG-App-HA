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

export function AIAssessmentBox({ deck }: Props) {
  if (!deck.ai_assessment) {
    return <Caption1 style={{ opacity: 0.5, display: 'block', marginTop: 12 }}>No AI assessment yet. Ask the MCP assistant to analyze this deck.</Caption1>;
  }

  return (
    <div style={{ marginTop: 12, padding: 12, borderRadius: 8, background: 'var(--colorNeutralBackground3, #f5f5f5)' }}>
      <Caption1 style={{ display: 'block', marginBottom: 6, opacity: 0.6 }}>
        AI Assessment {deck.ai_assessment_updated_at && `· ${timeAgo(deck.ai_assessment_updated_at)}`}
      </Caption1>
      <div className={styles.markdownContent}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {deck.ai_assessment}
        </ReactMarkdown>
      </div>
    </div>
  );
}
