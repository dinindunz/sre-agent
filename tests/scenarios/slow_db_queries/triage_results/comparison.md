# Scenario 1: Slow DB Queries - Human SRE vs Agent Cost & Time Comparison

| Source | Reference |
|---|---|
| Token costs | `src/agent/config.py` - `MODEL_PRICING` |
| Token usage | `triage_results/agent.py` - actual run |
| Infrastructure pricing | AWS bulk pricing API (ap-southeast-2) |
| AgentCore wall-clock | `triage_results/agent.py` - `"Invocation completed successfully (51.012s)"` |

---

## Agent - Actual Token Usage

From the final summary line in `agent.py`:

```
Input:      14,397 tokens    @ $0.003  /1K  =  $0.043191
Output:      2,622 tokens    @ $0.015  /1K  =  $0.039330
CacheRead:  21,202 tokens    @ $0.0003 /1K  =  $0.006361
CacheWrite: 16,539 tokens    @ $0.00375/1K  =  $0.062021
                                         ────────────────
Bedrock total:                               $0.150903
Cache net savings:                          -$0.044841
```

- **Wall-clock:** 51.012 seconds
- **Tool calls:** 7 - `load_skill` → `list_log_groups` → 4× `query_logs` → `post_jira_comment`
- **Cycles:** 5

### Per-Cycle Cost Breakdown

| Cycle | Action | Cost |
|---|---|---|
| 1 | `load_skill` | $0.018279 |
| 2 | `list_log_groups` | $0.023093 |
| 3 | 4× `query_logs` (parallel) | $0.028062 |
| 4 | `post_jira_comment` | $0.050111 |
| 5 | final response | $0.031358 |
| **Total** | | **$0.150903** |

---

## Infrastructure Costs Per Incident

### 1. API Gateway (REST)

**Pricing source:** https://aws.amazon.com/api-gateway/pricing/

| Item | Quantity | Unit price | Cost |
|---|---|---|---|
| POST /webhook | 1 request | $3.50 / 1M calls | **$0.0000035** |

### 2. Lambda - `jira-webhook`

**Pricing source:** https://aws.amazon.com/lambda/pricing/ (AWS Lambda bulk pricing API ap-southeast-2)

Config from `stack.py`: 256 MB memory, 60s timeout. Lambda does: HMAC validation → Cognito `list_users` → Cognito token request → AgentCore HTTP call (`stream=True`, returns on response headers) → returns 202.

Estimated execution: **~2 seconds warm** (based on code analysis - no actual Lambda CloudWatch metrics available), ~4–6 seconds cold start.

| Item | Calculation | Cost |
|---|---|---|
| Duration | 0.25 GB × 2s = 0.5 GB-s × $0.0000166667 | $0.0000083 |
| Request | $0.20 / 1M | $0.0000002 |
| **Total** | | **$0.0000085** |

### 3. Cognito - M2M Token Request

**Pricing source:** https://aws.amazon.com/cognito/pricing/ (AWS Cognito bulk pricing API ap-southeast-2)

Two operations per incident:

- **`list_users`** - verifies the Jira user against the pool. Charged per MAU, not per API call. For an automated system with no human sign-ins, MAU cost is $0.
- **OAuth2 token request** (client credentials grant) - M2M pricing:

| Tier | Monthly range | Price per request |
|---|---|---|
| Tier 1 | First 250,000 | $0.00225 |
| Tier 2 | 250K – 5M | $0.0015 |
| Tier 3 | 5M+ | $0.001125 |

The OAuth cache (`OAUTH_CACHE_BUFFER_PERCENT`, `OAUTH_CACHE_BUFFER_MIN_SEC`) avoids refetching a token on every invocation within the 15-minute token TTL. If multiple incidents arrive within that window, they share one token. For isolated incidents, the full **$0.00225** applies.

### 4. CloudWatch Logs Insights

**Pricing source:** https://aws.amazon.com/cloudwatch/pricing/ (AWS CloudWatch bulk pricing API ap-southeast-2)

$0.005 per GB of data scanned. 4 queries fired in parallel (api-service, db-primary, notification-service, payment-service - db-replica-1 not queried by the tightened skill in this run).

> **Note:** Data scanned per query depends on log group size and time window. The test scenario JSONL files are < 50 KB each. In production with a 60-minute window, 1–50 MB per query is typical. The estimate below uses 10 MB as a midpoint.

| Item | Calculation | Cost |
|---|---|---|
| 4 queries × ~10 MB each (estimated) | 0.04 GB × $0.005 / GB | **$0.0002000** |

Free tier: first 5 GB scanned/month free.

### 5. AgentCore Runtime

**Pricing source:** https://aws.amazon.com/bedrock/agentcore/pricing/

Consumption-based, billed per second for active CPU and peak memory consumed, with a 1-second minimum. I/O wait periods incur no CPU charges if idle — meaning time waiting for Bedrock inference and CloudWatch query results is excluded. For an LLM agent, the majority of wall-clock time is I/O wait.

- Wall-clock: 51.012 seconds (from agent.py)
- Assumed config: **2 vCPU / 4 GB memory**

| Resource | Rate |
|---|---|
| CPU | $0.0895 per vCPU-hour ($0.00002486 / vCPU-second) |
| Memory | $0.00945 per GB-hour ($0.000002625 / GB-second) |

**Active CPU estimate:** ~15 seconds of the 51s wall-clock (remainder is I/O wait on Bedrock and CloudWatch). This is conservative — actual active time may be lower. Memory is billed on peak consumption across the full session.

| Item | Calculation | Cost |
|---|---|---|
| CPU (active) | 2 vCPU × 15s × $0.00002486 | $0.000746 |
| Memory (peak, full wall-clock) | 4 GB × 51s × $0.000002625 | $0.000536 |
| **Total AgentCore** | | **$0.001282** |

Even billing the full 51s wall-clock for both CPU and memory yields $0.006594 — still under 5% of the Bedrock cost.

### 6. Bedrock - Claude Sonnet 4.5 (au cross-region inference)

**Pricing source:** `src/agent/config.py` - `MODEL_PRICING`

```python
"input":       $0.003   per 1K tokens  ($3.00  / 1M)
"output":      $0.015   per 1K tokens  ($15.00 / 1M)
"cache_write": $0.00375 per 1K tokens  ($3.75  / 1M)
"cache_read":  $0.0003  per 1K tokens  ($0.30  / 1M)
```

| Token type | Tokens | Rate | Cost |
|---|---|---|---|
| Input | 14,397 | $0.003/1K | $0.043191 |
| Output | 2,622 | $0.015/1K | $0.039330 |
| Cache read | 21,202 | $0.0003/1K | $0.006361 |
| Cache write | 16,539 | $0.00375/1K | $0.062021 |
| **Total Bedrock** | | | **$0.150903** |

Cache write front-loads cost in cycle 1; cycles 2–5 benefit from cheap cache reads at $0.0003/1K vs $0.003/1K regular input - a 10× saving on reused tokens.

---

## Total Per Incident

| Service | Cost | Source | % of total |
|---|---|---|---|
| API Gateway | $0.0000035 | WebFetch verified | 0.002% |
| Lambda | $0.0000085 | Bulk pricing API verified | 0.006% |
| Cognito M2M | $0.0022500 | Bulk pricing API verified | 1.5% |
| CloudWatch Logs Insights | $0.0002000 | Bulk pricing API verified | 0.1% |
| AgentCore Runtime (2 vCPU / 4 GB) | $0.0012820 | AgentCore pricing page | 0.8% |
| **Bedrock - Claude Sonnet 4.5** | **$0.150903** | **`config.py` + `agent.py` actual** | **97.6%** |
| **Total** | **$0.154647** | | |

**Bedrock is ~98% of the total. AgentCore Runtime (2 vCPU / 4 GB, ~15s active CPU) adds ~$0.0013 per incident.**

---

## Human SRE - Realistic Timeline

*(from `human.py`)*

Alert: `[ALERT] api-service CPU utilization above 85% - production` (91%, threshold 85%)

The CPU alert is deliberately ambiguous - high CPU could be a traffic surge, a slow dependency holding connections open, or a runaway process. The human must investigate to find the DB root cause.

| Phase | Time |
|---|---|
| Alert triage - check deploys, rule out traffic spike | 5–10 min |
| Check metrics dashboard - discover error rate spike | 3–5 min |
| Pull and read api-service logs | 5 min |
| Realise DB is the bottleneck, pull db-primary logs | 5 min |
| Investigate notification-service red herring | 5–10 min |
| Understand `auto_explain` Seq Scan output | 5–10 min |
| Confirm diagnosis with `EXPLAIN ANALYZE` | 5 min |
| Decide on safe fix, get approval | 5–10 min |
| **Total** | **38–60 min** |

The extra 3–5 minutes vs a "500 error" alert comes from the indirection: a CPU alert doesn't point at the DB. The SRE must first discover that CPU is high *because* of the DB issue, not the other way around.

### When the human knows it's a missing index

**Step 4** - reading the `auto_explain` Seq Scan output in `db-primary` logs. Still requires one manual step (`\d orders` to confirm no index exists on `customer_id`) before declaring root cause in the incident channel.

| Experience level | Time to diagnose |
|---|---|
| Junior SRE | 2–4 hours (doesn't recognise Seq Scan; may escalate to DBA) |
| Senior SRE | 38–60 min (recognises Seq Scan; still runs `EXPLAIN ANALYZE` to confirm) |
| With APM dashboards | 5–10 min (slow query surfaced before manual log digging) |

**SRE salary:** $150K/yr ÷ 2,080 hrs = **$72/hr**
**Cost of a 45-min incident:** $72 × 0.75 = **$54** (without on-call premium)

> On-call premium (nights/weekends) typically adds 1.5–2× to the hourly rate but is excluded here for a conservative comparison.

---

## Head-to-Head

| Dimension | Human SRE | Agent |
|---|---|---|
| Time to diagnose | 38–60 min | **51 seconds** |
| Cost per incident | $46–72 (without on-call premium) | **$0.15** |
| Red herrings | Investigated (5–10 min lost) | Dismissed immediately |
| Availability | On-call rotation | Always on, no paging required |
| Consistency | Varies by shift | Same reasoning every invocation |
| Jira comment | Written after triage | Posted automatically as part of triage |
| Schema check | Ran `\d orders` manually | Inferred from `Seq Scan` + `rows=1284901` |

---

## Monthly Projection

SRE: $150K/yr = $72/hr, 45-min avg incident = $54/incident (without on-call premium).
Agent: $0.154647 per incident.

| Incidents / month | AWS Cost | Human SRE Cost | Saving |
|---|---|---|---|
| 10 | $1.55 | $540 | ~$538 |
| 50 | $7.73 | $2,700 | ~$2,692 |
| 200 | $30.93 | $10,800 | ~$10,769 |
| 1,000 | $154.65 | $54,000 | ~$53,845 |

> Agent handles first-response triage only. Senior SRE still required for fix execution, change management, and post-mortems.

---

## Cost Reduction Levers

Bedrock = 98.4% of the known bill. All meaningful optimisation is here.

| Lever | Saving | Status |
|---|---|---|
| `thinking_budget_tokens` 8000 → 4000 | ~$0.030/incident (~20%) | Available in `config/dev.yaml` |
| Tighter skill prompt | Already applied | Was 15 tool calls, now 7 |
| Narrower CloudWatch query time window | Negligible at current scale | Available in `cloudwatch.py` |
| OAuth token caching | Already applied | `OAUTH_CACHE_BUFFER_PERCENT = 10%` amortises Cognito M2M cost |
