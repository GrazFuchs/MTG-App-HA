import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
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
  const queryClient = useQueryClient();
  const [msg, setMsg] = useState<string | null>(null);

  const { data: status, isLoading: statusLoading } = useQuery<SyncStatus>({
    queryKey: ['sync-status'],
    queryFn: () => api.getSyncStatus(),
    staleTime: 10_000,
  });
  const { data: history = [], isLoading: historyLoading } = useQuery<SyncLogEntry[]>({
    queryKey: ['sync-history'],
    queryFn: () => api.getSyncHistory(),
    staleTime: 30_000,
  });

  const loading = statusLoading || historyLoading;

  const syncMutation = useMutation({
    mutationFn: () => api.triggerSync(),
    onSuccess: () => {
      setMsg('Sync started. Refresh in a moment to see results.');
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['sync-status'] });
        queryClient.invalidateQueries({ queryKey: ['sync-history'] });
        queryClient.invalidateQueries({ queryKey: ['stats'] });
        queryClient.invalidateQueries({ queryKey: ['collection'] });
        queryClient.invalidateQueries({ queryKey: ['decks'] });
      }, 5000);
    },
    onError: (e: any) => {
      if (e.message?.includes('409')) {
        setMsg('A sync is already in progress. Please wait for it to finish.');
      } else {
        setMsg(`Error: ${e.message}`);
      }
    },
  });

  const resyncMutation = useMutation({
    mutationFn: () => api.triggerResync(),
    onSuccess: () => {
      setMsg('Full resync started. All data will be re-downloaded. Refresh in a moment.');
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['sync-status'] });
        queryClient.invalidateQueries({ queryKey: ['sync-history'] });
        queryClient.invalidateQueries({ queryKey: ['stats'] });
        queryClient.invalidateQueries({ queryKey: ['collection'] });
        queryClient.invalidateQueries({ queryKey: ['decks'] });
      }, 8000);
    },
    onError: (e: any) => {
      if (e.message?.includes('409')) {
        setMsg('A sync is already in progress. Please wait for it to finish.');
      } else {
        setMsg(`Error: ${e.message}`);
      }
    },
  });

  const syncing = syncMutation.isPending;
  const resyncing = resyncMutation.isPending;

  if (loading) return <Spinner label={t('common.loading')} />;

  return (
    <div>
      <PageHeader eyebrow="↯ SYSTEMS" title={t('settings.title')} accent={accent.oklch} />

      {msg && (
        <MessageBar intent="info" style={{ marginTop: 8, marginBottom: 16 }}>
          <MessageBarBody>{msg}</MessageBarBody>
        </MessageBar>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16, marginBottom: 24 }}>
        {/* Sync Configuration */}
        <Panel corners glow>
          <div style={{ fontFamily: sothera.fontMono, fontSize: 10, letterSpacing: 2, color: sothera.fgFaint, textTransform: 'uppercase', marginBottom: 12 }}>{t('settings.schedule')}</div>
          <div style={{ fontFamily: sothera.fontDisplay, fontSize: 20, fontWeight: 600, color: sothera.fg, marginBottom: 16 }}>{t('settings.sync_config')}</div>

          {[
            { label: 'Archidekt', value: status?.archidekt_username || t('settings.not_configured'), ok: !!status?.archidekt_username },
            { label: t('settings.auth'), value: status?.archidekt_authenticated ? t('settings.credentials_set') : t('settings.public_only'), ok: !!status?.archidekt_authenticated },
            { label: 'Cardmarket', value: status?.cardmarket_configured ? t('settings.username_set') : t('settings.not_configured'), ok: !!status?.cardmarket_configured },
            { label: t('settings.autosync'), value: status?.sync_enabled ? `Enabled · daily at ${status.next_sync_hour}:00` : t('settings.disabled'), ok: !!status?.sync_enabled },
          ].map(row => (
            <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: `1px solid ${sothera.rowBorder}` }}>
              <span style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted, letterSpacing: 1 }}>{row.label}</span>
              <span style={{ fontFamily: sothera.fontMono, fontSize: 11, color: row.ok ? sothera.positive : accent.oklch, letterSpacing: 0.5 }}>{row.value}</span>
            </div>
          ))}

          <div style={{ fontFamily: sothera.fontMono, fontSize: 10, color: sothera.fgFainter, marginTop: 12, letterSpacing: 0.5 }}>{t('settings.sync_config_hint')}</div>

          <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
            <Button icon={<ArrowSync24Regular />} appearance="primary" onClick={() => { setMsg(null); syncMutation.mutate(); }} disabled={syncing || resyncing}>
              {syncing ? t('settings.syncing') : t('settings.sync_now')}
            </Button>
            <Button icon={<DeleteRegular />} appearance="secondary" onClick={() => {
              if (!confirm('This will delete all synced data and re-download everything from Archidekt. Continue?')) return;
              setMsg(null);
              resyncMutation.mutate();
            }} disabled={syncing || resyncing}>
              {resyncing ? t('settings.resyncing') : t('settings.full_resync')}
            </Button>
          </div>
        </Panel>

        {/* Cardmarket Data */}
        <Panel>
          <div style={{ fontFamily: sothera.fontMono, fontSize: 10, letterSpacing: 2, color: sothera.fgFaint, textTransform: 'uppercase', marginBottom: 12 }}>{t('settings.connections')}</div>
          <div style={{ fontFamily: sothera.fontDisplay, fontSize: 20, fontWeight: 600, color: sothera.fg, marginBottom: 16 }}>{t('settings.cardmarket_data')}</div>
          <div style={{ fontFamily: sothera.fontBody, fontSize: 13, color: sothera.fgMuted, marginBottom: 16 }}>{t('settings.clear_hint')}</div>
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
            {t('settings.clear_all')}
          </Button>
        </Panel>
      </div>

      {/* Sync History */}
      <SectionHeader num="01" title={t('settings.history')} right={`${history.length} RECORDS`} accent={accent.oklch} />
      {history.length === 0 ? (
        <div style={{ fontFamily: sothera.fontMono, fontSize: 13, color: sothera.fgMuted, marginTop: 12, letterSpacing: 1 }}>{t('settings.history_empty')}</div>
      ) : (
        <Panel>
          {/* Six columns do not fit a phone. Scroll the table, not the page. */}
          <div style={{ overflowX: 'auto' }}>
          <div style={{ minWidth: 640 }}>
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
            <div>{t('col.started')}</div><div>{t('col.source')}</div><div>{t('col.status')}</div><div>{t('col.items')}</div><div>{t('col.finished')}</div><div>{t('col.error')}</div>
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
          </div>
          </div>
        </Panel>
      )}

      {/* Backup & Restore */}
      <SectionHeader num="02" title={t('settings.backup')} accent={accent.oklch} />
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
                setMsg(t('settings.restore_failed', { error: data.error || t('settings.unknown_error') }));
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
