import { QUESTIONS, describe } from './pilot';
import type { Telemetry, PilotResponse, ChoiceAnswer } from '../src/types';

/**
 * The same six questions answered by DeepSeek V4.1 Flash on Fireworks, with the recipe used in
 * ~/jevlab/app.py (benchmarks 1 to 3):
 *   logprobs  one request per question, max_tokens 1, reasoning off, option letter probabilities read from
 *             top_logprobs. Jev's exact interface (a real distribution per question), six calls in parallel.
 *   json      one request for all six questions, JSON mode, the model states a letter and a confidence p.
 *             The distribution is p on the chosen option and (1-p) spread over the others.
 */
const MODEL = 'accounts/fireworks/models/deepseek-v4p1-flash';
const URL = 'https://api.fireworks.ai/inference/v1/chat/completions';
const LETTERS = 'ABCDEFGH';
export type Recipe = 'logprobs' | 'json';

type Q = { type: 'choice'; instructions: string; criteria: Record<string, string> } | { type: 'boolean'; instructions: string };

function options(q: Q): string[] {
  return q.type === 'boolean' ? ['yes', 'no'] : Object.keys(q.criteria);
}
function block(q: Q): string {
  const opts = options(q);
  const lines = opts.map((o, i) => `${LETTERS[i]}. ${o}` + (q.type === 'choice' ? `: ${q.criteria[o]}` : '')).join('\n');
  const kind = q.type === 'boolean' ? 'Is the following statement about the state true?' : 'Question:';
  return `${kind} ${q.instructions}\n${lines}`;
}

async function chat(apiKey: string, body: Record<string, unknown>) {
  const res = await fetch(URL, {
    method: 'POST',
    headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: MODEL, temperature: 0, reasoning_effort: 'none', ...body }),
  });
  if (!res.ok) throw new Error(`fireworks ${res.status}: ${(await res.text()).slice(0, 200)}`);
  return res.json() as Promise<{
    choices: { message: { content: string }; logprobs?: { content: { top_logprobs: { token: string; logprob: number }[] }[] } }[];
    usage: { prompt_tokens: number; completion_tokens: number };
  }>;
}

async function askLogprobs(apiKey: string, state: string, q: Q) {
  const opts = options(q);
  const prompt = `State:\n${state}\n\n${block(q)}\n\nReply with exactly one letter from A-${LETTERS[opts.length - 1]} and nothing else.`;
  const r = await chat(apiKey, { messages: [{ role: 'user', content: prompt }], max_tokens: 1, logprobs: true, top_logprobs: 5 });
  const probs: Record<string, number> = Object.fromEntries(opts.map((o) => [o, 0]));
  for (const e of r.choices[0].logprobs?.content?.[0]?.top_logprobs ?? []) {
    const tok = e.token.trim().toUpperCase();
    if (tok.length === 1 && LETTERS.slice(0, opts.length).includes(tok)) probs[opts[LETTERS.indexOf(tok)]] += Math.exp(e.logprob);
  }
  const z = Object.values(probs).reduce((a, b) => a + b, 0) || 1;
  for (const o of opts) probs[o] /= z;
  return { probs, usage: r.usage };
}

function toChoice<K extends string>(probs: Record<string, number>): ChoiceAnswer<K> {
  const choice = Object.keys(probs).reduce((a, b) => (probs[b] > probs[a] ? b : a)) as K;
  return { choice, probabilities: probs as Record<K, number>, confidence: probs[choice] };
}

export function createDeepSeekHandler(apiKey: string | undefined, recipe: Recipe) {
  if (!apiKey) throw new Error('FIREWORKS_API_KEY is not set');
  const ids = Object.keys(QUESTIONS) as (keyof typeof QUESTIONS)[];

  return async function handle(telemetry: Telemetry): Promise<PilotResponse> {
    const situation = describe(telemetry);
    const state = JSON.stringify(situation, null, 2);
    const started = performance.now();
    const probs: Record<string, Record<string, number>> = {};
    let usage = { inputTokens: 0, outputTokens: 0 };

    if (recipe === 'logprobs') {
      const results = await Promise.all(ids.map((id) => askLogprobs(apiKey, state, QUESTIONS[id] as Q)));
      ids.forEach((id, i) => (probs[id] = results[i].probs));
      usage = {
        inputTokens: results.reduce((s, r) => s + r.usage.prompt_tokens, 0),
        outputTokens: results.reduce((s, r) => s + r.usage.completion_tokens, 0),
      };
    } else {
      const blocks = ids.map((id) => `[${id}] ${block(QUESTIONS[id] as Q)}`).join('\n\n');
      const prompt =
        `State:\n${state}\n\nAnswer every question below from the state.\n\n${blocks}\n\n` +
        'Reply with a single JSON object mapping each question id to {"a": <one letter>, "p": <your probability, 0 to 1, that the letter is correct>}. No other text.';
      const r = await chat(apiKey, {
        messages: [{ role: 'user', content: prompt }],
        max_tokens: 40 * ids.length + 50,
        response_format: { type: 'json_object' },
      });
      const parsed = JSON.parse(r.choices[0].message.content) as Record<string, { a?: string; p?: number }>;
      for (const id of ids) {
        const opts = options(QUESTIONS[id] as Q);
        const a = parsed[id] ?? {};
        let letter = String(a.a ?? '').trim().toUpperCase().slice(0, 1);
        let p = Math.min(Math.max(Number(a.p ?? 1), 0), 1);
        if (!LETTERS.slice(0, opts.length).includes(letter)) { letter = 'A'; p = 0; }
        const pick = opts[LETTERS.indexOf(letter)];
        const rest = opts.length > 1 ? (1 - p) / (opts.length - 1) : 0;
        probs[id] = Object.fromEntries(opts.map((o) => [o, o === pick ? p : rest]));
      }
      usage = { inputTokens: r.usage.prompt_tokens, outputTokens: r.usage.completion_tokens };
    }

    return {
      answers: {
        throttle: toChoice(probs.throttle),
        yaw: toChoice(probs.yaw),
        pitch: toChoice(probs.pitch),
        roll: toChoice(probs.roll),
        commitToLanding: probs.commitToLanding.yes,
        cutMotors: probs.cutMotors.yes,
      },
      usage,
      latencyMs: performance.now() - started,
      situation,
    };
  };
}
