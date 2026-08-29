import { useEffect, useState } from 'react';
import {
  Title3,
  Body1,
  Caption1,
  Button,
  Card,
  Badge,
  Accordion,
  AccordionItem,
  AccordionHeader,
  AccordionPanel,
  MessageBar,
  MessageBarBody,
} from '@fluentui/react-components';
import { api, MCPSetupInstructions } from '../../api';

import { t } from '../../i18n';
export function MCPSetupSection() {
  const [data, setData] = useState<MCPSetupInstructions | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getMcpSetupInstructions()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleCopy = async () => {
    if (!data) return;
    await navigator.clipboard.writeText(JSON.stringify(data.config_example, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) return null;
  if (error) return (
    <Card style={{ padding: 16, marginTop: 24 }}>
      <Title3>{t('mcp.title')}</Title3>
      <MessageBar intent="error" style={{ marginTop: 8 }}>
        <MessageBarBody>Failed to load setup info: {error}</MessageBarBody>
      </MessageBar>
    </Card>
  );
  if (!data) return null;

  return (
    <Card style={{ padding: 16, marginTop: 24 }}>
      <Title3>{t('mcp.title')}</Title3>
      <Body1 style={{ marginTop: 8 }}>
        {/* This section only renders after /setup-instructions answered, so
            "reachable" is earned, not hardcoded. The MCP endpoint is /mcp
            (streamable HTTP) — an earlier version displayed a nonexistent
            /mcp/sse here. */}
        Status: <Badge appearance="filled" color="success">{t('mcp.reachable')}</Badge>
        {' · '}
        <Caption1>MCP-Endpoint (via Ingress): {data.mcp_ingress_path}</Caption1>
        {data.auth_required && (
          <>
            {' · '}
            <Badge appearance="outline" color="warning">{t('mcp.token_required')}</Badge>
          </>
        )}
      </Body1>

      <div style={{ marginTop: 16 }}>
        <Body1><strong>{t('mcp.step', { n: 1 })}</strong> {t('mcp.step1')}</Body1>
        <div style={{ marginTop: 8 }}>
          <Button
            appearance="primary"
            size="small"
            onClick={() => {
              const a = document.createElement('a');
              a.href = data.download_url;
              a.download = 'mcp-proxy.mjs';
              a.click();
            }}
          >
            ⬇ mcp-proxy.mjs herunterladen
          </Button>
        </div>
      </div>

      <div style={{ marginTop: 16 }}>
        <Body1><strong>{t('mcp.step', { n: 2 })}</strong> {t('mcp.step2')}</Body1>
        <Caption1 style={{ display: 'block', marginTop: 4 }}>
          {t('mcp.step2_hint')}
        </Caption1>
      </div>

      <div style={{ marginTop: 16 }}>
        <Body1><strong>{t('mcp.step', { n: 3 })}</strong> {t('mcp.step3')}</Body1>
        <pre style={{
          marginTop: 8,
          padding: 12,
          borderRadius: 6,
          background: 'var(--colorNeutralBackground3, #f5f5f5)',
          overflow: 'auto',
          fontSize: 12,
          maxHeight: 200,
        }}>
          {JSON.stringify(data.config_example, null, 2)}
        </pre>
        <Button
          size="small"
          appearance="secondary"
          onClick={handleCopy}
          style={{ marginTop: 4 }}
        >
          {copied ? '✓ Copied!' : '📋 Copy to clipboard'}
        </Button>
      </div>

      <div style={{ marginTop: 16 }}>
        <Body1><strong>{t('mcp.step', { n: 4 })}</strong> {t('mcp.step4')}</Body1>
        <Accordion collapsible>
          <AccordionItem value="paths">
            <AccordionHeader size="small">{t('mcp.show_paths')}</AccordionHeader>
            <AccordionPanel>
              <Caption1 style={{ display: 'block' }}>
                <strong>macOS:</strong> {data.config_paths.macos}
              </Caption1>
              <Caption1 style={{ display: 'block', marginTop: 4 }}>
                <strong>Windows:</strong> {data.config_paths.windows}
              </Caption1>
              <Caption1 style={{ display: 'block', marginTop: 4 }}>
                <strong>Linux:</strong> {data.config_paths.linux}
              </Caption1>
            </AccordionPanel>
          </AccordionItem>
        </Accordion>
      </div>

      <div style={{ marginTop: 16 }}>
        <Body1><strong>{t('mcp.step', { n: 5 })}</strong> {t('mcp.step5')}</Body1>
        <Caption1 style={{ display: 'block', marginTop: 4 }}>
          Replace {'<PATH_TO>'} with the full path to your saved mcp-proxy.mjs file, and {'<TODO: your long-lived token>'} with the token from Step 2.
        </Caption1>
      </div>

      <div style={{ marginTop: 16 }}>
        <Body1><strong>{t('mcp.step', { n: 6 })}</strong> {t('mcp.step6')}</Body1>
        <Caption1 style={{ display: 'block', marginTop: 4 }}>
          {t('mcp.step6_hint')}
        </Caption1>
      </div>
    </Card>
  );
}
