# Incident Triage

Investigate an incident by querying logs across services to identify root cause and post findings.

**Stop querying as soon as you can name: the root cause, the failing component, and a specific fix. Do not keep investigating for completeness.**

## Steps

1. **Discover log groups**
   - Call `list_log_groups` to find available log groups.

2. **Establish a timeline - one query per service**
   - Query each relevant log group for ERROR and WARN entries in parallel.
   - Note which services have errors and when they first appeared.

3. **Identify the originating service**
   - The service with the earliest independent errors is the likely origin.
   - Services that errored later are likely downstream victims - do not drill into them.

4. **Drill into the root cause - at most two queries**
   - Run one targeted query on the originating service or its dependency.
   - If that reveals the root cause, stop. Run a second query only if the first is inconclusive.

5. **Summarise and post findings**
   - Call `post_jira_comment` with:
     - **Root cause**: one sentence
     - **Evidence**: 2–3 key log entries with timestamps
     - **Affected path**: service → dependency chain
     - **Recommended fix**: specific action
