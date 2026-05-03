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
      <Title3>MCP Setup for Claude Desktop</Title3>
      <MessageBar intent="error" style={{ marginTop: 8 }}>
        <MessageBarBody>Failed to load setup info: {error}</MessageBarBody>
      </MessageBar>
    </Card>
  );
  if (!data) return null;

  return (
    <Card style={{ padding: 16, marginTop: 24 }}>
      <Title3>MCP Setup for Claude Desktop</Title3>
      <Body1 style={{ marginTop: 8 }}>
        Status: <Badge appearance="filled" color="success">MCP Server running</Badge>
        {' · '}
        <Caption1>Endpoint: {data.download_url.replace('/api/mcp/proxy.mjs', '/mcp/sse')}</Caption1>
      </Body1>

      <div style={{ marginTop: 16 }}>
        <Body1><strong>Step 1:</strong> Download proxy file</Body1>
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
        <Body1><strong>Step 2:</strong> Create a Long-Lived Access Token</Body1>
        <Caption1 style={{ display: 'block', marginTop: 4 }}>
          In Home Assistant: Profile → Security → Long-Lived Access Tokens → Create Token
        </Caption1>
      </div>

      <div style={{ marginTop: 16 }}>
        <Body1><strong>Step 3:</strong> Paste config into Claude Desktop</Body1>
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
        <Body1><strong>Step 4:</strong> Config file location</Body1>
        <Accordion collapsible>
          <AccordionItem value="paths">
            <AccordionHeader size="small">Show paths per OS</AccordionHeader>
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
        <Body1><strong>Step 5:</strong> Replace placeholders in the config</Body1>
        <Caption1 style={{ display: 'block', marginTop: 4 }}>
          Replace {'<PATH_TO>'} with the full path to your saved mcp-proxy.mjs file, and {'<TODO: your long-lived token>'} with the token from Step 2.
        </Caption1>
      </div>

      <div style={{ marginTop: 16 }}>
        <Body1><strong>Step 6:</strong> Restart Claude Desktop</Body1>
        <Caption1 style={{ display: 'block', marginTop: 4 }}>
          After saving the config, fully quit and reopen Claude Desktop.
        </Caption1>
      </div>
    </Card>
  );
}
