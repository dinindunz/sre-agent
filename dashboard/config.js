/**
 * Bedrock Agent Cost Calculator - Pricing Configuration
 *
 * Update this file when AWS pricing changes.
 * All model prices are per 1M tokens (USD).
 * AgentCore rates are USD.
 *
 * Sources:
 *   - AgentCore: https://aws.amazon.com/bedrock/agentcore/pricing/
 *   - Bedrock:   https://aws.amazon.com/bedrock/pricing/
 *   - Region:    Asia Pacific (Sydney)
 *   - Last updated: April 2026
 */
const CONFIG = {

  // USD to AUD conversion rate
  audRate: 1.55,

  // ── Bedrock Model Pricing (USD per 1M tokens, Sydney) ──
  models: {
    sonnet46: {
      name: 'Claude Sonnet 4.6',
      global: { input: 3.00, output: 15.00, cache5m: 3.75, cache1h: 6.00, cacheRead: 0.30 },
      geo:    { input: 3.30, output: 16.50, cache5m: 4.125, cache1h: 6.60, cacheRead: 0.33 }
    },
    opus46: {
      name: 'Claude Opus 4.6',
      global: { input: 5.00, output: 25.00, cache5m: 6.25, cache1h: 10.00, cacheRead: 0.50 },
      geo:    { input: 5.50, output: 27.50, cache5m: 6.875, cache1h: 11.00, cacheRead: 0.55 }
    },
    haiku45: {
      name: 'Claude Haiku 4.5',
      global: { input: 1.00, output: 5.00, cache5m: 1.25, cache1h: 2.00, cacheRead: 0.10 },
      geo:    { input: 1.10, output: 5.50, cache5m: 1.375, cache1h: 2.20, cacheRead: 0.11 }
    }
  },

  // ── AgentCore Pricing (USD) ──
  agentCore: {
    // Runtime, Browser Tool, Code Interpreter (same rates)
    cpu: 0.0895,           // per vCPU-hour
    mem: 0.00945,          // per GB-hour

    // Gateway
    gwApi: 0.005,          // per 1,000 API invocations (ListTools, InvokeTool, Ping)
    gwSearch: 0.025,       // per 1,000 Search API invocations
    gwIndex: 0.02,         // per 100 tools indexed per month

    // Memory
    memShortTerm: 0.25,    // per 1,000 new events
    memLongBuiltin: 0.75,  // per 1,000 memory records stored per month (built-in strategies)
    memLongSelf: 0.25,     // per 1,000 memory records stored per month (self-managed)
    memRetrieval: 0.50,    // per 1,000 memory record retrievals

    // Identity (free when used via Runtime or Gateway)
    identityToken: 0.010   // per 1,000 token/API key requests (non-AWS resources only)
  },

  // ── Complexity Presets ──
  presets: {
    light:    { prompt: 2000, newPerCycle: 100, outputPerCycle: 80,  cycles: 2 },
    standard: { prompt: 3500, newPerCycle: 150, outputPerCycle: 100, cycles: 5 },
    heavy:    { prompt: 5000, newPerCycle: 250, outputPerCycle: 150, cycles: 8 }
  }
};
