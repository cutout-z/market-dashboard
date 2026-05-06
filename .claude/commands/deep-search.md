# Deep Search — Market Event Intelligence

Rapid multi-source intelligence sweep triggered by a material market event.

## Step 1 — Get the Trigger

Ask the user:

> **What's the trigger?**
> Describe the event in one line — e.g. "live news that Trump has directed USA to invade Iran", "Fed emergency rate cut 50bps", "Tether depegged to $0.94"

The user may also pass the trigger as an argument: `$ARGUMENTS`

If `$ARGUMENTS` is non-empty, use that as the trigger. Otherwise, ask and wait for their response before proceeding.

## Step 2 — Fan Out (Parallel Research)

Once you have the trigger, launch **up to 4 research agents in parallel** using the Agent tool. Each agent gets the trigger context and a specific research focus.

### Agent 1: Web Search — Breaking News
- Use WebSearch to find the latest reporting on the trigger event
- Search queries: the trigger text verbatim, plus 2-3 variant queries (e.g. add "market reaction", "breaking", key entity names)
- Extract: what happened, when, who confirmed it, which sources are reporting
- Flag: is this confirmed or unconfirmed/rumour? Single-source or multi-source?

### Agent 2: Polymarket — Prediction Market Response
- Use the Polymarket CLI (`/opt/homebrew/bin/polymarket`) to search for related markets:
  - `polymarket markets search "<key terms from trigger>" -o json`
  - `polymarket events list --active true --order volume --limit 20 -o json` — scan top events for relevance
- For any matching markets: extract current odds, volume, recent price movement
- If Polymarket API is unreachable, note this and skip

### Agent 3: Market Impact Assessment
- Use the OpenBB MCP tools to check price action on assets most likely affected by the trigger:
  - `mcp__openbb__equity_price_quote` for key indices (SPY, QQQ, DIA), VIX, relevant sector ETFs
  - `mcp__openbb__equity_price_quote` for commodities (GLD, CL=F, TLT) and crypto (BTC-USD) if relevant
  - `mcp__openbb__equity_discovery_active` for most active stocks (may show related names)
- Compare current prices to prior close — is the market already reacting?
- If markets are closed, note this and check futures if possible

### Agent 4: Geopolitical / Contextual Background
- Use WebSearch to find background context: prior precedents, historical analogues, expert analysis
- Search for: "[trigger] analysis", "[trigger] implications", "[trigger] precedent"
- Summarise: what does this mean, what are the second-order effects, what should be watched next

## Step 3 — Synthesise

Compile all agent results into a structured briefing. Output format:

```
## DEEP SEARCH: [trigger event — one line]
**Time:** [current timestamp]
**Confidence:** [CONFIRMED / UNCONFIRMED / DEVELOPING]

### What Happened
[2-3 sentences — the facts as currently known]

### Source Assessment
- **Confirmed by:** [list sources]
- **First reported:** [source + time if known]
- **Status:** [confirmed / single-source / rumour / developing]

### Market Reaction
| Asset | Price | Change | Signal |
|-------|-------|--------|--------|
| [relevant assets] | ... | ... | ... |

### Prediction Markets
| Market | Odds | Volume | Move |
|--------|------|--------|------|
| [relevant Polymarket events] | ... | ... | ... |

### Second-Order Effects
- [bullet list of implications — what happens next, what to watch]

### Historical Precedent
- [closest analogues and how markets reacted then]

### Watch List
- [ ] [specific things to monitor in the next 1-24 hours]
```

## Step 4 — Save to Dashboard (Optional)

If the market dashboard is running (check if port 8060 is active), write the briefing to the news cache so it appears in the News & Alerts panel:

Write a JSON file to `/Users/zalen/Documents/Zalen/AI Wif Brain Projects/market-dashboard/app/data/cache/deep_search_latest.json` with the briefing content.

## Rules
- Speed over polish — this is a time-sensitive operation
- Always lead with the confidence assessment (confirmed vs rumour)
- If any agent fails or times out, proceed with what you have — partial intel is better than waiting
- Do NOT speculate beyond what the sources say — flag uncertainty explicitly
- Keep the briefing scannable — busy professionals need to absorb this in 60 seconds
