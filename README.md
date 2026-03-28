# Matter Node Pinger for Home Assistant


> [!WARNING]
> **Experimental workaround only**
>
> This add-on is **experimental** and is intended only as a temporary workaround / test tool while the underlying issue is investigated.
>
> Using periodic **pinging** and **re-interviewing** generates additional traffic on the **Thread** network. On larger or busier networks, or when used against multiple devices, this may introduce extra load, reduce stability, and create side effects of its own.
>
> It may also have a **negative impact on battery-powered devices**, as increased activity can reduce battery life.
>
> Because of this, it should be used **carefully**, only on **specific problem devices**, and not as a broad or permanent solution for an entire Matter / Thread deployment.
>
> The real goal is still to identify and fix the **root cause**, rather than rely on repeated reads, pinging, or re-interviews long term.

A small custom Home Assistant add-on that connects to the Matter Server WebSocket, discovers commissioned Matter nodes, and can periodically **ping** and **re-interview** selected devices.

This was built mainly to help test and work around reliability issues with some **sleepy IKEA Matter over Thread devices** such as:

- **BILRESA scroll wheel**
- **TIMMERFLOTTE temperature / humidity sensor**
- other IKEA Matter devices that show up cleanly in Matter Server discovery

## What it does

The add-on runs on a schedule and can:

- discover commissioned Matter nodes from Home Assistant Matter Server
- filter devices by text match, such as `BILRESA` or `TIMMERFLOTTE`
- or target exact Matter node IDs
- ping each selected node
- retry if a ping fails
- request a re-interview of the node
- verify whether the **Last Interview** timestamp advanced
- write clear, human-readable logs so you can see what matched and what was acted on

## Why use this

Some battery-powered Matter devices can appear to stay online but stop updating reliably until they are refreshed. This add-on gives you an easy way to test whether periodic pinging and re-interviewing improves stability.

It is intended as a **practical workaround / test tool**, not a permanent fix for every Matter issue.

## Features

- clean structured logging
- timestamps on all log lines
- discovery logs with readable device names
- bridge devices excluded from text matching
- explicit **Matched** / **Not Matched** filter decisions
- ping retry handling
- interview verification using **Last Interview Before** and **Last Interview After**
- works well for mixed IKEA device filters such as:

```yaml
match: BILRESA,TIMMERFLOTTE
```

## Requirements

- Home Assistant OS or a Home Assistant installation with add-on support
- the official **Matter Server** add-on already installed and working
- a commissioned Matter fabric with devices already paired into Home Assistant

## Installation

### Option 1: Local custom add-on

1. Open the Home Assistant `addons` share.
2. Create a folder for the add-on, for example:

```text
addons/matter_node_pinger/
```

3. Place the add-on files in that folder:

```text
config.yaml
Dockerfile
run.sh
pinger.py
README.md
```

4. In Home Assistant, go to:

**Settings → Add-ons → Add-on Store**

5. Open the menu and click:

**Check for updates**

6. The add-on should appear under **Local add-ons**.
7. Install it.

### Option 2: Samba share

If you use the Samba add-on, open the `addons` share from your PC and copy the add-on folder there.

Example Windows path:

```text
\\homeassistant.local\addons
```

or

```text
\\<home-assistant-ip>\addons
```

## Basic configuration

Start with discovery mode first:

```yaml
ws_url: ws://core-matter-server:5580/ws
match: BILRESA
node_ids: ""
interval_seconds: 120
ping_attempts: 3
delay_seconds: 0.5
list_only: true
```

### What the options mean

- `ws_url`  
  Matter Server WebSocket URL.

- `match`  
  Comma-separated device text filter.  
  Example: `BILRESA,TIMMERFLOTTE`

- `node_ids`  
  Exact Matter node IDs to target.  
  Example: `"29,41"`

- `interval_seconds`  
  How often the add-on runs.

- `ping_attempts`  
  Number of ping attempts per request.

- `delay_seconds`  
  Delay between ping and interview.

- `list_only`  
  If `true`, the add-on only discovers and logs devices.  
  If `false`, it will actively ping and interview the selected nodes.

## Recommended first run

Use:

```yaml
list_only: true
```

Then start the add-on and check the logs.

You should see readable discovery lines like:

```text
[DISCOVERY] Node 29: IKEA of Sweden | BILRESA scroll wheel | button | P2.0 | 1.9.11 | E2490
[FILTER] Node 29: MATCHED — matched filter term(s) ['BILRESA']
```

This helps you confirm:

- which devices were found
- which devices matched your filter
- which devices would be targeted

## Match mode vs fixed node IDs

You can select devices in two ways.

### Match mode

Example:

```yaml
match: BILRESA,TIMMERFLOTTE
node_ids: ""
```

This is useful when you want the add-on to automatically target devices whose names contain those terms.

### Fixed node IDs

Example:

```yaml
match: ""
node_ids: "29,41"
```

This is the safest option when you already know the exact node IDs.

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

### BILRESA + TIMMERFLOTTE

```yaml
ws_url: ws://core-matter-server:5580/ws
match: BILRESA,TIMMERFLOTTE
node_ids: ""
interval_seconds: 120
ping_attempts: 3
delay_seconds: 0.5
list_only: false
```

### Exact node IDs only

```yaml
ws_url: ws://core-matter-server:5580/ws
match: ""
node_ids: "29,41"
interval_seconds: 120
ping_attempts: 3
delay_seconds: 0.5
list_only: false
```

## How the logs work

The logs are split into clear sections such as:

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

Shows a clean, readable summary of each end device.

Example:

```text
[DISCOVERY] Node 41: IKEA of Sweden | BILRESA scroll wheel | button | P2.0 | 1.8.7 | E2490
```

### Filter

Shows whether a device matched your filter.

Example:

```text
[FILTER] Node 41: MATCHED — matched filter term(s) ['BILRESA']
```

or

```text
[FILTER] Node 42: NOT MATCHED — no filter terms matched
```

### Action

Shows ping and interview activity.

Example:

```text
[ACTION] Node 29: Ping starting
[ACTION] Node 29: Ping result = {"fdd6:...": true}
[ACTION] Node 29: Interview starting
[ACTION] Node 29: Interview result = Completed (no response details returned)
```

### Verify

After an interview, the add-on can compare the **Last Interview** timestamp before and after so you can see whether Matter Server actually refreshed its record.

Example:

```text
[VERIFY] Node 29: Last Interview Before = 2026-03-24T23:03:40.000000
[VERIFY] Node 29: Last Interview After  = 2026-03-24T23:03:51.000000
[VERIFY] Node 29: Interview Verified    = Yes
```

## Bridge behaviour

Bridge nodes are still discovered internally, but:

- they are omitted from the detailed discovery logs
- they are ignored by text matching

This helps prevent a bridge from being accidentally targeted just because its payload contains metadata for bridged child devices.

## Ping retry behaviour

If a ping fails or times out, the add-on can retry and log that cleanly.

This is useful for sleepy or occasionally slow Thread devices.

## Updating the add-on

If you modify `pinger.py`, `run.sh`, or other add-on files:

1. bump the version in `config.yaml`
2. go to **Settings → Add-ons → Add-on Store**
3. click **Check for updates**
4. rebuild / restart the add-on

## Troubleshooting

### The add-on does not appear in Home Assistant

- make sure the folder is in the `addons` share
- make sure `config.yaml` is valid
- click **Check for updates**
- refresh the browser

### The add-on fails to build

Check the Supervisor logs and confirm your Dockerfile and architecture values are correct for your Home Assistant installation.

### The add-on connects but no devices are matched

Run with:

```yaml
list_only: true
```

Then check the `DISCOVERY` and `FILTER` logs to confirm the exact names and match basis being used.

### The interview result says “Completed (no response details returned)”

That is expected. `interview_node` is a side-effect action and may not return a detailed payload. The important part is whether:

- the command completes successfully
- the node remains reachable
- the **Last Interview** timestamp advances afterward

### A device still drops out

Try:

- lowering `interval_seconds`
- using exact `node_ids` instead of `match`
- watching the **Verify** log lines to see whether interviews are actually refreshing the node
- checking general Thread / Matter stability separately

## Notes

- ANSI colours may not always display in the Home Assistant log viewer, depending on how logs are rendered.
- Even if colours do not render, the log labels remain readable and structured.
- This project is intended as a practical utility for testing and improving Matter device reliability in Home Assistant.

## Example repository structure

```text
matter_node_pinger/
├── config.yaml
├── Dockerfile
├── run.sh
├── pinger.py
└── README.md
```

## License

Add your preferred license here.
