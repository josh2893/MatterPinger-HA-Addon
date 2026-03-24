#!/usr/bin/with-contenv bashio

APP_NAME="Matter Node Pinger"

log_info() {
    bashio::log.info "[Launcher] $*"
}

log_warn() {
    bashio::log.warning "[Launcher] $*"
}

export WS_URL="$(bashio::config 'ws_url')"
export MATCH="$(bashio::config 'match')"
export NODE_IDS="$(bashio::config 'node_ids')"
export INTERVAL_SECONDS="$(bashio::config 'interval_seconds')"
export PING_ATTEMPTS="$(bashio::config 'ping_attempts')"
export DELAY_SECONDS="$(bashio::config 'delay_seconds')"
export LIST_ONLY="$(bashio::config 'list_only')"

log_info "Starting ${APP_NAME}"
log_info "Configuration loaded successfully"
log_info "Structured logging will now continue in pinger.py"

if [ -z "${WS_URL}" ]; then
    log_warn "Matter Server URL is empty. The add-on may not be able to connect."
fi

exec python3 /pinger.py
