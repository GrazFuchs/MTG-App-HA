import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Caption1 } from '@fluentui/react-components';
import { DeckDetail } from '../../api';
import styles from './AIAssessmentBox.module.css';

import { t } from '../../i18n';
interface Props {
  deck: DeckDetail;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return t('time.minutes_ago', { n: mins });
  const hours = Math.floor(mins / 60);
  if (hours < 24) return t('time.hours_ago', { n: hours });
  const days = Math.floor(hours / 24);
  return t('time.days_ago', { n: days });
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
    return <Caption1 style={{ opacity: 0.5, display: 'block', marginTop: 12 }}>{t('ai.empty')}</Caption1>;
  }

  /**
   * An assessment written before the deck was last edited describes a list that
   * no longer exists. Measured on 2026-08-29: of the four decks that have one,
   * *all four* predate their deck's last change — so without this the box shows
   * a confident paragraph about a deck as it was in June and says nothing about
   * that being the case.
   *
   * `updated_at` is Archidekt's edit timestamp, which is what "the deck
   * changed" means here; `last_synced` would only say when we last looked.
   */
  const stale = Boolean(
    deck.ai_assessment_updated_at && deck.updated_at
    && new Date(deck.ai_assessment_updated_at) < new Date(deck.updated_at),
  );

  return (
    <div style={{ marginTop: 12, padding: 12, borderRadius: 8, background: 'var(--colorNeutralBackground3, #f5f5f5)' }}>
      <button
        type="button"
        onClick={toggle}
        aria-expanded={expanded}
        style={{
          cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8,
          background: 'transparent', border: 'none', padding: 0, font: 'inherit',
          color: 'inherit', textAlign: 'left', width: '100%',
        }}
      >
        <span aria-hidden="true" style={{ fontSize: 12, color: 'var(--colorNeutralForeground3, #888)', transition: 'transform 0.2s', transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
        <Caption1 style={{ opacity: 0.6 }}>
          {t('ai.title')} {deck.ai_assessment_updated_at && `· ${timeAgo(deck.ai_assessment_updated_at)}`}
        </Caption1>
        {stale && (
          <Caption1
            title={t('ai.stale_hint')}
            style={{
              marginLeft: 4, padding: '1px 6px', borderRadius: 3,
              background: 'rgba(224,160,32,0.18)', color: '#e0a020',
              border: '1px solid rgba(224,160,32,0.45)', whiteSpace: 'nowrap',
            }}
          >
            {t('ai.stale')}
          </Caption1>
        )}
      </button>
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
