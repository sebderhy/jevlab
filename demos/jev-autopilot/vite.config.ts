import { defineConfig, loadEnv, type Plugin } from 'vite';
import type { IncomingMessage, ServerResponse } from 'node:http';
import { appendFileSync, mkdirSync } from 'node:fs';
import { createPilotHandler } from './server/pilot';
import { createDeepSeekHandler } from './server/deepseek';
import { createLayaHandler } from './server/laya';
import type { Telemetry, PilotResponse } from './src/types';

/**
 * Dev-server middleware that proxies autopilot decisions to the chosen pilot. API keys stay server-side.
 *   POST /api/pilot?pilot=jev            TypeSafe Jev through the AI SDK (the original demo)
 *   POST /api/pilot?pilot=deepseek       DeepSeek V4.1 Flash on Fireworks, logprobs recipe
 *   POST /api/pilot?pilot=deepseek-json  DeepSeek V4.1 Flash on Fireworks, JSON mode
 *   POST /api/pilot?pilot=laya           Laya 421M on this box's CPU via the jevlab app (port 3210)
 *   POST /api/pilot?pilot=decider        Decider-2B on this box's CPU via jevlab local_server (port 3211)
 *   POST /api/flight                     appends one finished flight (JSON) to runs/flights.jsonl
 */
function pilotApi(env: Record<string, string>): Plugin {
  const handlers: Record<string, ((t: Telemetry) => Promise<PilotResponse>) | undefined> = {};
  const get = (name: string) => {
    if (!handlers[name]) {
      if (name === 'jev') handlers[name] = createPilotHandler(env.TYPESAFE_AI_API_KEY);
      else if (name === 'deepseek') handlers[name] = createDeepSeekHandler(env.FIREWORKS_API_KEY, 'logprobs');
      else if (name === 'deepseek-json') handlers[name] = createDeepSeekHandler(env.FIREWORKS_API_KEY, 'json');
      else if (name === 'laya') handlers[name] = createLayaHandler('laya');
      else if (name === 'decider') handlers[name] = createLayaHandler('decider');
      else throw new Error(`unknown pilot "${name}"`);
    }
    return handlers[name]!;
  };
  const readBody = (req: IncomingMessage) =>
    new Promise<string>((resolve) => {
      let body = '';
      req.on('data', (c) => (body += c));
      req.on('end', () => resolve(body));
    });
  return {
    name: 'pilot-api',
    configureServer(server) {
      server.middlewares.use('/api/pilot', async (req: IncomingMessage, res: ServerResponse) => {
        if (req.method !== 'POST') { res.statusCode = 405; res.end(); return; }
        const pilot = new URL(req.url ?? '/', 'http://x').searchParams.get('pilot') ?? 'jev';
        const body = await readBody(req);
        try {
          const result = await get(pilot)(JSON.parse(body));
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify(result));
        } catch (err) {
          console.error(`[pilot ${pilot}]`, err instanceof Error ? err.message : err);
          res.statusCode = 500;
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify({ error: err instanceof Error ? err.message : String(err) }));
        }
      });
      server.middlewares.use('/api/flight', async (req: IncomingMessage, res: ServerResponse) => {
        if (req.method !== 'POST') { res.statusCode = 405; res.end(); return; }
        const body = await readBody(req);
        mkdirSync('runs', { recursive: true });
        appendFileSync('runs/flights.jsonl', JSON.stringify({ at: new Date().toISOString(), ...JSON.parse(body) }) + '\n');
        console.info('[flight]', body);
        res.end('ok');
      });
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [pilotApi(env)],
    server: { port: Number(env.PORT) || 5173, strictPort: true },
  };
});
