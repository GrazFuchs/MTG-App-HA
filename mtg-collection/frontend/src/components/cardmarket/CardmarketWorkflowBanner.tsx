import { useState } from 'react';
import {
  Body1,
  Caption1,
  Button,
  Card,
  Title3,
} from '@fluentui/react-components';

import { t } from '../../i18n';
const STORAGE_KEY = 'cardmarket_banner_dismissed';

interface Props {
  onImport: () => void;
  onExport: () => void;
  exporting: boolean;
  hasListings: boolean;
}

export function CardmarketWorkflowBanner({ onImport, onExport, exporting, hasListings }: Props) {
  const [dismissed, setDismissed] = useState(() =>
    localStorage.getItem(STORAGE_KEY) === 'true'
  );

  if (dismissed) {
    return (
      <Caption1
        style={{ display: 'block', marginBottom: 8, cursor: 'pointer', opacity: 0.5 }}
        onClick={() => { localStorage.removeItem(STORAGE_KEY); setDismissed(false); }}
      >
        ℹ️ Show Cardmarket workflow guide
      </Caption1>
    );
  }

  return (
    <Card style={{ padding: 16, marginTop: 12, marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Title3>📋 Cardmarket Workflow</Title3>
        <Button
          size="small"
          appearance="subtle"
          onClick={() => { localStorage.setItem(STORAGE_KEY, 'true'); setDismissed(true); }}
        >
          {t('common.hide')}
        </Button>
      </div>
      <Caption1 style={{ display: 'block', marginTop: 4, opacity: 0.7 }}>
        {t('cardmarket.workflow_intro')}
      </Caption1>

      <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <Body1>
          <strong>①</strong> {t('cardmarket.workflow_step1')}
          <Caption1 style={{ display: 'block', marginLeft: 20 }}>{t('cardmarket.workflow_step1_hint')}</Caption1>
        </Body1>

        <Body1>
          <strong>②</strong> Import here:{' '}
          <Button size="small" appearance="primary" onClick={onImport}>
            📤 Import CSV
          </Button>
          <Caption1 style={{ display: 'block', marginLeft: 20 }}>{t('cardmarket.workflow_step2_hint')}</Caption1>
        </Body1>

        <Body1>
          <strong>③</strong> {t('cardmarket.workflow_step3')}
        </Body1>

        <Body1>
          <strong>④</strong> Re-Export:{' '}
          <Button size="small" appearance="secondary" onClick={onExport} disabled={exporting || !hasListings}>
            ⬇ Export as CSV
          </Button>
          <Caption1 style={{ display: 'block', marginLeft: 20 }}>{t('cardmarket.workflow_step4_hint')}</Caption1>
        </Body1>

        <Body1>
          <strong>⑤</strong> {t('cardmarket.workflow_step5')}
        </Body1>
      </div>
    </Card>
  );
}
