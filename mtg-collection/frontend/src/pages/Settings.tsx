import { useEffect, useState } from 'react';
import {
  Spinner,
  Button,
  MessageBar,
  MessageBarBody,
} from '@fluentui/react-components';
import { ArrowSync24Regular, DeleteRegular } from '@fluentui/react-icons';
import { api, SyncStatus, SyncLogEntry } from '../api';
import { t } from '../i18n';
import { MCPSetupSection } from '../components/settings/MCPSetupSection';
import { sothera } from '../theme/sothera';
import { useAccent } from '../main';
import { Panel, PageHeader, SectionHeader } from '../components/sothera';

export default function Settings() {
  const { accent } = useAccent();
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
      <PageHeader eyebrow="↯ SYSTEMS" title={t('settings.title')} accent={accent.oklch} />

      {msg && (
        <MessageBar intent="info" style={{ marginTop: 8, marginBottom: 16 }}>
          <MessageBarBody>{msg}</MessageBarBody>
        </MessageBar>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
        {/* Sync Configuration */}
        <Panel corners glow>
          <div style={{ fontFamily: sothera.fontMono, fontSize: 10, letterSpacing: 2, color: sothera.fgFaint, textTransform: 'uppercase', marginBottom: 12 }}>SYNC SCHEDULE</div>
          <div style={{ fontFamily: sothera.fontDisplay, fontSize: 20, fontWeight: 600, color: sothera.fg, marginBottom: 16 }}>Sync Configuration</div>

          {[
            { label: 'Archidekt', value: status?.archidekt_username || 'Not configured', ok: !!status?.archidekt_username },
            { label: 'Auth', value: status?.archidekt_authenticated ? 'Credentials set' : 'Public only', ok: !!status?.archidekt_authenticated },
            { label: 'Cardmarket', value: status?.cardmarket_configured ? 'Username set' : 'Not configured', ok: !!status?.cardmarket_configured },
            { label: 'Auto-sync', value: status?.sync_enabled ? `Enabled · daily at ${status.next_sync_hour}:00` : 'Disabled', ok: !!status?.sync_enabled },
          ].map(row => (
            <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: `1px solid ${sothera.rowBorder}` }}>
              <span style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted, letterSpacing: 1 }}>{row.label}</span>
              <span style={{ fontFamily: sothera.fontMono, fontSize: 11, color: row.ok ? sothera.positive : accent.oklch, letterSpacing: 0.5 }}>{row.value}</span>
            </div>
          ))}

          <div style={{ fontFamily: sothera.fontMono, fontSize: 10, color: sothera.fgFainter, marginTop: 12, letterSpacing: 0.5 }}>Configure these options in the Home Assistant Add-on settings.</div>

          <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
            <Button icon={<ArrowSync24Regular />} appearance="primary" onClick={handleSync} disabled={syncing || resyncing}>
              {syncing ? 'Syncing...' : 'Sync Now'}
            </Button>
            <Button icon={<DeleteRegular />} appearance="secondary" onClick={handleResync} disabled={syncing || resyncing}>
              {resyncing ? 'Resyncing...' : 'Full Resync'}
            </Button>
          </div>
        </Panel>

        {/* Cardmarket Data */}
        <Panel>
          <div style={{ fontFamily: sothera.fontMono, fontSize: 10, letterSpacing: 2, color: sothera.fgFaint, textTransform: 'uppercase', marginBottom: 12 }}>CONNECTIONS</div>
          <div style={{ fontFamily: sothera.fontDisplay, fontSize: 20, fontWeight: 600, color: sothera.fg, marginBottom: 16 }}>Cardmarket Data</div>
          <div style={{ fontFamily: sothera.fontBody, fontSize: 13, color: sothera.fgMuted, marginBottom: 16 }}>Delete all Cardmarket listings (both imported and manually created).</div>
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
        </Panel>
      </div>

      {/* Sync History */}
      <SectionHeader num="01" title="Sync History" right={`${history.length} RECORDS`} accent={accent.oklch} />
      {history.length === 0 ? (
        <div style={{ fontFamily: sothera.fontMono, fontSize: 13, color: sothera.fgMuted, marginTop: 12, letterSpacing: 1 }}>No sync history yet.</div>
      ) : (
        <Panel>
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1.5fr 80px 80px 70px 1.5fr 2fr',
            padding: '4px 0 14px',
            borderBottom: `1px solid ${sothera.headerBorder}`,
            fontFamily: sothera.fontMono,
            fontSize: 9,
            letterSpacing: 2,
            color: sothera.fgFaint,
            textTransform: 'uppercase',
          }}>
            <div>STARTED</div><div>SOURCE</div><div>STATUS</div><div>ITEMS</div><div>FINISHED</div><div>ERROR</div>
          </div>
          {history.map((h) => (
            <div key={h.id} style={{
              display: 'grid',
              gridTemplateColumns: '1.5fr 80px 80px 70px 1.5fr 2fr',
              padding: '12px 0',
              borderBottom: `1px solid ${sothera.rowBorder}`,
              fontSize: 13,
              alignItems: 'center',
            }}>
              <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>{new Date(h.started_at).toLocaleString()}</div>
              <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>{h.source}</div>
              <div>
                <span style={{
                  fontFamily: sothera.fontMono,
                  fontSize: 9,
                  padding: '2px 6px',
                  letterSpacing: 1.5,
                  borderWidth: 1,
                  borderStyle: 'solid',
                  borderColor: h.status === 'success' ? sothera.positive : h.status === 'running' ? accent.oklch : sothera.negative,
                  color: h.status === 'success' ? sothera.positive : h.status === 'running' ? accent.oklch : sothera.negative,
                }}>
                  {h.status.toUpperCase()}
                </span>
              </div>
              <div style={{ fontFamily: sothera.fontDisplay, fontWeight: 600, color: sothera.fg, fontFeatureSettings: '"tnum"' }}>{h.items_synced}</div>
              <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>{h.finished_at ? new Date(h.finished_at).toLocaleString() : '—'}</div>
              <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{h.error || '—'}</div>
            </div>
          ))}
        </Panel>
      )}

      {/* Backup & Restore */}
      <SectionHeader num="02" title="Backup & Restore" accent={accent.oklch} />
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

      <MCPSetupSection />
    </div>
  );
}
