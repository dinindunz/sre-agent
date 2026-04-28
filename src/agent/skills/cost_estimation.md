# Cost Estimation

Estimate the per-invocation AWS consumption cost for an agent use case based on published pricing.

**Produce a cost breakdown table. State assumptions clearly. Flag any inputs you had to estimate.**

## Pricing Reference

Source: https://aws.amazon.com/bedrock/agentcore/pricing/

### AgentCore Runtime

| Resource | Rate |
|---|---|
| CPU | $0.0895 per vCPU-hour ($0.00002486 per vCPU-second) |
| Memory | $0.00945 per GB-hour ($0.000002625 per GB-second) |

- Billed per second, 1-second minimum.
- CPU is billed on **active consumption only** — I/O wait (model inference, API calls) incurs no CPU charge.
- Memory is billed on **peak consumption** across the session lifetime.
- 128 MB minimum memory billing applies.

### Bedrock - Model Inference

| Model | Input | Output | Cache Write | Cache Read |
|---|---|---|---|---|
| Claude Sonnet 4.5 (cross-region) | $3.00/1M | $15.00/1M | $3.75/1M | $0.30/1M |

Token estimates by use-case complexity:

| Complexity | Input tokens | Output tokens | Cycles | Typical wall-clock |
|---|---|---|---|---|
| Simple (1-2 tool calls) | 5,000-10,000 | 1,000-2,000 | 2-3 | 15-30s |
| Medium (3-7 tool calls) | 10,000-20,000 | 2,000-4,000 | 4-6 | 30-60s |
| Complex (8+ tool calls) | 20,000-50,000 | 4,000-8,000 | 6-10 | 60-120s |

### API Gateway (REST)

| Item | Rate |
|---|---|
| API calls | $3.50 per 1M requests |

### Lambda

| Item | Rate |
|---|---|
| Duration | $0.0000166667 per GB-second |
| Requests | $0.20 per 1M requests |

### Cognito M2M (OAuth token)

| Tier | Monthly range | Rate |
|---|---|---|
| Tier 1 | First 250,000 | $0.00225 per request |
| Tier 2 | 250K-5M | $0.0015 per request |
| Tier 3 | 5M+ | $0.001125 per request |

### CloudWatch Logs Insights

| Item | Rate |
|---|---|
| Data scanned | $0.005 per GB |

First 5 GB scanned per month is free.

## Steps

1. **Identify the use case parameters**
   - Number of tool calls and which tools are used.
   - Estimated active CPU time vs wall-clock time (for LLM agents, active CPU is typically 20-30% of wall-clock).
   - AgentCore runtime config: vCPU count and memory allocation.
   - Model and expected token usage (input, output, cache).

2. **Calculate AgentCore Runtime cost**
   - CPU cost = vCPUs x active_seconds x $0.00002486
   - Memory cost = peak_GB x wall_clock_seconds x $0.000002625
   - State the active-CPU-to-wall-clock ratio assumption.

3. **Calculate Bedrock cost**
   - Input cost = input_tokens x rate / 1000
   - Output cost = output_tokens x rate / 1000
   - If prompt caching is used, split into cache_write (first cycle) and cache_read (subsequent cycles).
   - This is typically 95-99% of the total bill.

4. **Calculate infrastructure costs**
   - API Gateway: number of webhook calls x $3.50/1M
   - Lambda: memory_GB x duration_seconds x $0.0000166667
   - Cognito M2M: token requests x tier rate (account for caching if applicable)
   - CloudWatch: queries x estimated_data_scanned_GB x $0.005

5. **Produce the cost summary**
   - Present a table with: Service, Cost, % of total.
   - Show the per-invocation total.
   - Project monthly cost at 10, 50, 200, and 1,000 invocations.
   - Note which inputs are actual vs estimated.

6. **Identify cost reduction levers**
   - List the top 2-3 ways to reduce cost (e.g., fewer cycles, lower thinking budget, tighter skill prompts, token caching).
   - Quantify the potential saving where possible.
