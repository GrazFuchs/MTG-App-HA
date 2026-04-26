#!/usr/bin/env node
/**
 * Local MCP stdio proxy for HA ingress.
 * 
 * Authenticates with HA via WebSocket, creates an ingress session,
 * then proxies MCP messages between stdio and the add-on's HTTP endpoint.
 * 
 * Usage: node mcp-proxy.mjs <ha_url> <token> <ingress_path>
 * Example: node mcp-proxy.mjs http://10.0.0.101:8123 eyJ... /api/hassio_ingress/XXX/mcp/mcp
 */

import { createInterface } from 'readline';
import http from 'http';
import https from 'https';
import { URL } from 'url';

const HA_URL = process.argv[2];
const TOKEN = process.argv[3];
const INGRESS_PATH = process.argv[4];
const MCP_AUTH_TOKEN = process.argv[5] || process.env.MCP_AUTH_TOKEN || '';

if (!HA_URL || !TOKEN || !INGRESS_PATH) {
  process.stderr.write('Usage: node mcp-proxy.mjs <ha_url> <token> <ingress_path> [mcp_auth_token]\n');
  process.exit(1);
}

const baseUrl = new URL(HA_URL);
const mcpUrl = new URL(INGRESS_PATH, HA_URL);

let sessionCookie = null;
let sessionId = null;

function log(...args) {
  process.stderr.write(`[mcp-proxy] ${args.join(' ')}\n`);
}

/**
 * Create an ingress session via HA WebSocket API.
 */
async function createIngressSession() {
  const { default: WebSocket } = await import('ws');
  
  const wsUrl = `${baseUrl.protocol === 'https:' ? 'wss' : 'ws'}://${baseUrl.host}/api/websocket`;
  log(`Connecting to ${wsUrl}...`);
  
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    let msgId = 1;
    
    ws.on('message', (data) => {
      const msg = JSON.parse(data.toString());
      
      if (msg.type === 'auth_required') {
        ws.send(JSON.stringify({ type: 'auth', access_token: TOKEN }));
      } else if (msg.type === 'auth_ok') {
        log('Authenticated with HA');
        // Create ingress session
        ws.send(JSON.stringify({
          id: msgId++,
          type: 'supervisor/api',
          endpoint: '/ingress/session',
          method: 'post',
        }));
      } else if (msg.type === 'auth_invalid') {
        reject(new Error('Authentication failed: ' + msg.message));
        ws.close();
      } else if (msg.type === 'result') {
        const session = msg.result?.data?.session || msg.result?.session;
        if (msg.success && session) {
          sessionCookie = session;
          log(`Got ingress session: ${sessionCookie.slice(0, 16)}...`);
          ws.close();
          resolve(sessionCookie);
        } else {
          log('Session response:', JSON.stringify(msg));
          reject(new Error('Failed to create ingress session: ' + JSON.stringify(msg)));
          ws.close();
        }
      }
    });
    
    ws.on('error', (err) => {
      reject(new Error(`WebSocket error: ${err.message}`));
    });
    
    ws.on('close', () => {
      log('WebSocket closed');
    });
    
    setTimeout(() => reject(new Error('WebSocket timeout')), 15000);
  });
}

/**
 * Send an HTTP request to the MCP endpoint with the ingress session cookie.
 */
function mcpRequest(body, extraHeaders = {}) {
  return new Promise((resolve, reject) => {
    const url = mcpUrl;
    const mod = url.protocol === 'https:' ? https : http;
    
    const postData = JSON.stringify(body);
    
    const headers = {
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(postData),
      'Accept': 'application/json, text/event-stream',
      'Cookie': `ingress_session=${sessionCookie}`,
      ...(MCP_AUTH_TOKEN ? { 'Authorization': `Bearer ${MCP_AUTH_TOKEN}` } : {}),
      ...extraHeaders,
    };
    
    if (sessionId) {
      headers['Mcp-Session-Id'] = sessionId;
    }
    
    const req = mod.request(url, {
      method: 'POST',
      headers,
    }, (res) => {
      // Capture session ID from response
      const newSessionId = res.headers['mcp-session-id'];
      if (newSessionId) {
        sessionId = newSessionId;
      }
      
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        if (res.statusCode === 401 || res.statusCode === 403) {
          reject(new Error(`Auth error ${res.statusCode}: ${data}`));
          return;
        }
        if (res.statusCode >= 400) {
          reject(new Error(`HTTP ${res.statusCode}: ${data}`));
          return;
        }
        resolve({ status: res.statusCode, data, headers: res.headers });
      });
    });
    
    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

/**
 * Main proxy loop: read JSON-RPC from stdin, forward to HTTP, write response to stdout.
 */
async function main() {
  // Install ws package if needed
  try {
    await import('ws');
  } catch {
    log('Installing ws package...');
    const { execSync } = await import('child_process');
    execSync('npm install ws', { cwd: new URL('.', import.meta.url).pathname, stdio: 'pipe' });
  }
  
  // Create ingress session
  try {
    await createIngressSession();
  } catch (err) {
    log(`Failed to create ingress session: ${err.message}`);
    process.exit(1);
  }
  
  log('MCP proxy ready, reading from stdin...');
  
  const rl = createInterface({ input: process.stdin });
  
  for await (const line of rl) {
    if (!line.trim()) continue;
    
    let msg;
    try {
      msg = JSON.parse(line);
    } catch {
      log(`Invalid JSON: ${line}`);
      continue;
    }
    
    log(`→ ${msg.method || 'response'} (id=${msg.id})`);
    
    try {
      const resp = await mcpRequest(msg);
      
      // Handle SSE or JSON response
      if (resp.headers['content-type']?.includes('text/event-stream')) {
        // Parse SSE events
        const events = resp.data.split('\n');
        for (const event of events) {
          if (event.startsWith('data: ')) {
            const eventData = event.slice(6).trim();
            if (eventData) {
              log(`← event: ${eventData.slice(0, 100)}`);
              process.stdout.write(eventData + '\n');
            }
          }
        }
      } else {
        // Direct JSON response
        log(`← ${resp.data.slice(0, 100)}`);
        process.stdout.write(resp.data + '\n');
      }
    } catch (err) {
      log(`Error: ${err.message}`);
      
      // If auth error, try refreshing session
      if (err.message.includes('Auth error')) {
        log('Refreshing ingress session...');
        try {
          await createIngressSession();
          // Retry
          const resp = await mcpRequest(msg);
          process.stdout.write(resp.data + '\n');
        } catch (retryErr) {
          log(`Retry failed: ${retryErr.message}`);
          // Send error response
          if (msg.id !== undefined) {
            process.stdout.write(JSON.stringify({
              jsonrpc: '2.0',
              id: msg.id,
              error: { code: -32000, message: retryErr.message },
            }) + '\n');
          }
        }
      } else if (msg.id !== undefined) {
        process.stdout.write(JSON.stringify({
          jsonrpc: '2.0',
          id: msg.id,
          error: { code: -32000, message: err.message },
        }) + '\n');
      }
    }
  }
}

main().catch((err) => {
  log(`Fatal: ${err.message}`);
  process.exit(1);
});
