import { QUESTIONS, describe } from './pilot';
import type { Telemetry, PilotResponse, ChoiceAnswer } from '../src/types';

/**
 * The same six questions answered by Laya (convaiinnovations/laya, 421M ModernBERT-large, Apache 2.0), the open
 * zero-shot typed-decision model, served by the jevlab demo app on this box (CPU only, no GPU here).
 * The jevlab /decide endpoint speaks Jev's shape: choice questions carry an options dict, booleans are "noul".
 */
const URLS: Record<string, string> = { laya: 'http://127.0.0.1:3210/decide', decider: 'http://127.0.0.1:3211/decide' }; // jevlab app; local_server (Decider-2B)
type Q = { type: 'choice'; instructions: string; criteria: Record<string, string> } | { type: 'boolean'; instructions: string };

export function createLayaHandler(engine: 'laya' | 'decider' = 'laya') {
  const URL = URLS[engine];
  const questions = Object.fromEntries(
    Object.entries(QUESTIONS).map(([id, q]) => {
      const qq = q as Q;
      return [id, qq.type === 'boolean' ? { type: 'noul', instructions: qq.instructions } : { type: 'choice', instructions: qq.instructions, options: qq.criteria }];
    }),
  );
  return async function handle(telemetry: Telemetry): Promise<PilotResponse> {
    const situation = describe(telemetry);
    const started = performance.now();
    const res = await fetch(URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state: situation, questions, engines: [engine] }),
    });
    if (!res.ok) throw new Error(`${engine} ${res.status}: ${(await res.text()).slice(0, 200)}`);
    const r = (await res.json()) as { results: Record<string, { answers: Record<string, { answer: string | number; probabilities: Record<string, number>; confidence: number }> }> };
    const a = r.results[engine].answers;
    const choice = <K extends string>(id: string): ChoiceAnswer<K> => ({
      choice: a[id].answer as K,
      probabilities: a[id].probabilities as Record<K, number>,
      confidence: a[id].confidence,
    });
    return {
      answers: {
        throttle: choice('throttle'),
        yaw: choice('yaw'),
        pitch: choice('pitch'),
        roll: choice('roll'),
        commitToLanding: a.commitToLanding.probabilities.yes,
        cutMotors: a.cutMotors.probabilities.yes,
      },
      usage: { inputTokens: 0, outputTokens: 0 },
      latencyMs: performance.now() - started,
      situation,
    };
  };
}
