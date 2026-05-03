import { useEffect, useState } from 'react';
import {
  makeStyles,
  tokens,
  Title2,
  Title3,
  Body1,
  Caption1,
  Spinner,
  Button,
  Badge,
  Card,
  MessageBar,
  MessageBarBody,
  Table,
  TableHeader,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
  Divider,
} from '@fluentui/react-components';
import { ArrowSync24Regular, DeleteRegular } from '@fluentui/react-icons';
import { api, SyncStatus, SyncLogEntry } from '../api';
import { t } from '../i18n';
import { MCPSetupSection } from '../components/settings/MCPSetupSection';

const useStyles = makeStyles({
  section: {
    marginTop: '24px',
  },
  statusCard: {
    padding: '16px',
    marginTop: '12px',
  },
  tableWrap: {
    marginTop: '12px',
    overflowX: 'auto',
  },
});

export default function Settings() {
  const styles = useStyles();
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [history, setHistory] = useState<SyncLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [resyncing, setResyncing] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    Promise.all([api.getSyncStatus(), api.getSyncHistory()])
      .then(([s, h]) => { setStatus(s); setHistory(h); })
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleSync = async () => {
    setSyncing(true);
    setMsg(null);
    try {
      await api.triggerSync();
      setMsg('Sync started. Refresh in a moment to see results.');
      setTimeout(load, 5000);
    } catch (e: any) {
      if (e.message?.includes('409')) {
        setMsg('A sync is already in progress. Please wait for it to finish.');
      } else {
        setMsg(`Error: ${e.message}`);
      }
    } finally {
      setSyncing(false);
    }
  };

  const handleResync = async () => {
    if (!confirm('This will delete all synced data and re-download everything from Archidekt. Continue?')) return;
    setResyncing(true);
    setMsg(null);
    try {
      await api.triggerResync();
      setMsg('Full resync started. All data will be re-downloaded. Refresh in a moment.');
      setTimeout(load, 8000);
    } catch (e: any) {
      if (e.message?.includes('409')) {
        setMsg('A sync is already in progress. Please wait for it to finish.');
      } else {
        setMsg(`Error: ${e.message}`);
      }
    } finally {
      setResyncing(false);
    }
  };

  if (loading) return <Spinner label="Loading..." />;

  return (
    <div>
      <Title2>{t('settings.title')}</Title2>

      {msg && (
        <MessageBar intent="info" style={{ marginTop: 8 }}>
          <MessageBarBody>{msg}</MessageBarBody>
        </MessageBar>
      )}

      <Card className={styles.statusCard}>
        <Title3>Sync Configuration</Title3>
        <Body1 style={{ marginTop: 8 }}>
          Archidekt Username: <strong>{status?.archidekt_username || 'Not configured'}</strong>
          {' — '}
          Authentication:{' '}
          <Badge appearance="filled" color={status?.archidekt_authenticated ? 'success' : 'warning'}>
            {status?.archidekt_authenticated ? 'Credentials set' : 'Public only'}
          </Badge>
        </Body1>
        <br />
        <Body1>
          Cardmarket:{' '}
          <Badge appearance="filled" color={status?.cardmarket_configured ? 'success' : 'warning'}>
            {status?.cardmarket_configured ? 'Username set' : 'Not configured'}
          </Badge>
        </Body1>
        <br />
        <Body1>
          Auto-sync:{' '}
          <Badge appearance="filled" color={status?.sync_enabled ? 'success' : 'warning'}>
            {status?.sync_enabled ? 'Enabled' : 'Disabled'}
          </Badge>
          {status?.sync_enabled && ` — daily at ${status.next_sync_hour}:00`}
        </Body1>
        <br />
        <Caption1>Configure these options in the Home Assistant Add-on settings.</Caption1>
        <br /><br />
        <Button
          icon={<ArrowSync24Regular />}
          appearance="primary"
          onClick={handleSync}
          disabled={syncing || resyncing}
        >
          {syncing ? 'Syncing...' : 'Sync Now'}
        </Button>
        {' '}
        <Button
          icon={<DeleteRegular />}
          appearance="secondary"
          onClick={handleResync}
          disabled={syncing || resyncing}
        >
          {resyncing ? 'Resyncing...' : 'Full Resync'}
        </Button>
      </Card>

      <Card className={styles.statusCard}>
        <Title3>Cardmarket Data</Title3>
        <Body1 style={{ marginTop: 8 }}>Delete all Cardmarket listings (both imported and manually created).</Body1>
        <br />
        <Button
          icon={<DeleteRegular />}
          appearance="secondary"
          onClick={async () => {
            if (!confirm('Delete ALL Cardmarket listings? This cannot be undone.')) return;
            setMsg(null);
            try {
              await api.clearCardmarketListings();
              setMsg('All Cardmarket listings cleared.');
            } catch (e: any) {
              setMsg(`Error: ${e.message}`);
            }
          }}
        >
          Clear All Listings
        </Button>
      </Card>

      <div className={styles.section}>
        <Title3>Sync History</Title3>
        {history.length === 0 ? (
          <Body1 style={{ marginTop: 8 }}>No sync history yet.</Body1>
        ) : (
          <div className={styles.tableWrap}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHeaderCell>Started</TableHeaderCell>
                  <TableHeaderCell>Source</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                  <TableHeaderCell>Items</TableHeaderCell>
                  <TableHeaderCell>Finished</TableHeaderCell>
                  <TableHeaderCell>Error</TableHeaderCell>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.map((h) => (
                  <TableRow key={h.id}>
                    <TableCell>{new Date(h.started_at).toLocaleString()}</TableCell>
                    <TableCell>{h.source}</TableCell>
                    <TableCell>
                      <Badge appearance="filled" color={h.status === 'success' ? 'success' : h.status === 'running' ? 'brand' : 'danger'}>
                        {h.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{h.items_synced}</TableCell>
                    <TableCell>{h.finished_at ? new Date(h.finished_at).toLocaleString() : '—'}</TableCell>
                    <TableCell>{h.error || '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      {/* Backup & Restore */}
      <div className={styles.section}>
        <Title3>{t('settings.backup')}</Title3>
        <div style={{ display: 'flex', gap: 12, marginTop: 12, flexWrap: 'wrap' }}>
          <Button
            appearance="primary"
            onClick={() => {
              const a = document.createElement('a');
              const base = window.location.pathname.match(/^(\/api\/hassio_ingress\/[^/]+)/)?.[1] || '';
              a.href = `${base}/api/backup/backup`;
              a.click();
            }}
          >
            {t('settings.download_backup')}
          </Button>
          <Button
            appearance="secondary"
            onClick={() => {
              const input = document.createElement('input');
              input.type = 'file';
              input.accept = '.db';
              input.onchange = async () => {
                const file = input.files?.[0];
                if (!file) return;
                const form = new FormData();
                form.append('file', file);
                const base = window.location.pathname.match(/^(\/api\/hassio_ingress\/[^/]+)/)?.[1] || '';
                const resp = await fetch(`${base}/api/backup/restore`, { method: 'POST', body: form });
                const data = await resp.json();
                if (data.status === 'restored') {
                  setMsg(`Database restored (${data.size_bytes} bytes). Restart the add-on to apply.`);
                } else {
                  setMsg(`Restore failed: ${data.error || 'Unknown error'}`);
                }
              };
              input.click();
            }}
          >
            {t('settings.restore_backup')}
          </Button>
        </div>
      </div>

      <MCPSetupSection />
    </div>
  );
}
