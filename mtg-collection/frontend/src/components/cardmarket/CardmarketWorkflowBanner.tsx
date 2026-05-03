import { useState } from 'react';
import {
  Body1,
  Caption1,
  Button,
  Card,
  Title3,
} from '@fluentui/react-components';

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
          Hide
        </Button>
      </div>
      <Caption1 style={{ display: 'block', marginTop: 4, opacity: 0.7 }}>
        Cardmarket has no official sync API for stocks — updates work via CSV roundtrips:
      </Caption1>

      <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <Body1>
          <strong>①</strong> On cardmarket.com → Stock → "Export to CSV"
          <Caption1 style={{ display: 'block', marginLeft: 20 }}>Downloads your current stock list</Caption1>
        </Body1>

        <Body1>
          <strong>②</strong> Import here:{' '}
          <Button size="small" appearance="primary" onClick={onImport}>
            📤 Import CSV
          </Button>
          <Caption1 style={{ display: 'block', marginLeft: 20 }}>Updates your listings in this add-on</Caption1>
        </Body1>

        <Body1>
          <strong>③</strong> Edit here (adjust prices, mark cards for sale)
        </Body1>

        <Body1>
          <strong>④</strong> Re-Export:{' '}
          <Button size="small" appearance="secondary" onClick={onExport} disabled={exporting || !hasListings}>
            ⬇ Export as CSV
          </Button>
          <Caption1 style={{ display: 'block', marginLeft: 20 }}>CSV with your changes, ready for re-import on Cardmarket</Caption1>
        </Body1>

        <Body1>
          <strong>⑤</strong> On Cardmarket: use browser extension or MKM API for bulk updates (power users)
        </Body1>
      </div>
    </Card>
  );
}
