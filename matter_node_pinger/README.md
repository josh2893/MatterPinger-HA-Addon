# Matter Node Pinger

A custom Home Assistant add-on that connects to Matter Server, discovers your commissioned Matter devices, and can periodically ping and re-interview selected nodes.

This add-on is useful for testing and working around reliability issues with some Matter over Thread devices, especially battery-powered IKEA devices.

## What this add-on does

- Connects to the Matter Server WebSocket
- Discovers commissioned Matter nodes
- Lets you target devices by:
  - **Match text** such as `BILRESA` or `TIMMERFLOTTE`
  - **Exact Node IDs** such as `29,41`
- Pings selected nodes
- Retries failed pings
- Requests a re-interview of selected nodes
- Verifies whether **Last Interview** advanced
- Writes clear, human-readable logs

## First use

Start in discovery-only mode first.

Use this configuration:

```yaml
ws_url: ws://core-matter-server:5580/ws
match: BILRESA
node_ids: ""
interval_seconds: 120
ping_attempts: 3
delay_seconds: 0.5
list_only: true
```

Then:

1. Save the configuration
2. Start the add-on
3. Open the **Logs** tab

You should see discovery lines like:

```text
[DISCOVERY] Node 29: IKEA of Sweden | BILRESA scroll wheel | button | P2.0 | 1.9.11 | E2490
[FILTER] Node 29: MATCHED — matched filter term(s) ['BILRESA']
```

This lets you confirm:

- which devices were found
- which devices matched your filter
- which devices you want to target

## How to select devices

### Option 1: Match text

Example:

```yaml
match: BILRESA,TIMMERFLOTTE
node_ids: ""
```

This will target devices whose readable identity matches those terms.

### Option 2: Exact Node IDs

Example:

```yaml
match: ""
node_ids: "29,41"
```

This is the safest option once you already know the correct Node IDs.

## Recommended active configurations

### BILRESA only

```yaml
ws_url: ws://core-matter-server:5580/ws
match: BILRESA
node_ids: ""
interval_seconds: 120
ping_attempts: 3
delay_seconds: 0.5
list_only: false
```

### BILRESA and TIMMERFLOTTE

```yaml
ws_url: ws://core-matter-server:5580/ws
match: BILRESA,TIMMERFLOTTE
node_ids: ""
interval_seconds: 120
ping_attempts: 3
delay_seconds: 0.5
list_only: false
```

### Exact Node IDs

```yaml
ws_url: ws://core-matter-server:5580/ws
match: ""
node_ids: "29,41"
interval_seconds: 120
ping_attempts: 3
delay_seconds: 0.5
list_only: false
```

## Configuration options

### `ws_url`
Matter Server WebSocket URL.

Default:

```yaml
ws_url: ws://core-matter-server:5580/ws
```

### `match`
Comma-separated filter text used to match readable device names.

Examples:

```yaml
match: BILRESA
match: BILRESA,TIMMERFLOTTE
```

### `node_ids`
Comma-separated exact Matter Node IDs.

Example:

```yaml
node_ids: "29,41"
```

### `interval_seconds`
How often the add-on runs.

### `ping_attempts`
How many ping attempts Matter Server should make per request.

### `delay_seconds`
Delay between the ping and the interview action.

### `list_only`
If `true`, the add-on only discovers devices and logs what would match.

If `false`, the add-on actively pings and interviews the selected nodes.

## What the logs mean

The logs are grouped into sections:

- `STARTUP`
- `CYCLE`
- `CONNECTION`
- `DISCOVERY`
- `FILTER`
- `TARGETS`
- `ACTION`
- `VERIFY`
- `SLEEP`

### Discovery
Shows a clean summary of each end device.

Example:

```text
[DISCOVERY] Node 41: IKEA of Sweden | BILRESA scroll wheel | button | P2.0 | 1.8.7 | E2490
```

### Filter
Shows whether the device matched your filter.

Example:

```text
[FILTER] Node 41: MATCHED — matched filter term(s) ['BILRESA']
[FILTER] Node 42: NOT MATCHED — no filter terms matched
```

### Action
Shows the ping and interview activity.

Example:

```text
[ACTION] Node 29: Ping starting
[ACTION] Node 29: Ping result = {"fdd6:...": true}
[ACTION] Node 29: Interview starting
[ACTION] Node 29: Interview result = Completed (no response details returned)
```

### Verify
Shows whether the node's **Last Interview** timestamp advanced after the interview request.

Example:

```text
[VERIFY] Node 29: Last Interview Before = 2026-03-24T23:03:40.000000
[VERIFY] Node 29: Last Interview After  = 2026-03-24T23:03:51.000000
[VERIFY] Node 29: Interview Verified    = Yes
```

## Important notes

- Bridge nodes are ignored by text matching
- Bridge nodes are omitted from detailed discovery logs
- The Home Assistant log viewer may not always show ANSI colours
- Even without colour, the log formatting remains readable

## Troubleshooting

### Nothing matches
Set:

```yaml
list_only: true
```

Then check the **DISCOVERY** and **FILTER** log lines to see the exact device names being used.

### Interview result says "Completed (no response details returned)"
That is normal. The important part is whether the **Verify** section shows that **Last Interview** advanced.

### Ping failed or timed out
The add-on can retry failed pings and log that clearly. If failures continue, the device may be asleep, out of range, or having Thread connectivity issues.

## Tip

For the cleanest testing, start with discovery mode first, then switch to exact `node_ids` once you know the right devices.
