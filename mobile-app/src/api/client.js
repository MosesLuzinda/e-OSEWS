import AsyncStorage from "@react-native-async-storage/async-storage";
import Constants from "expo-constants";
import * as Network from "expo-network";

const FALLBACK_API_HOST = "192.168.1.67";

function resolveApiHost() {
  const hostUri =
    Constants?.expoConfig?.hostUri ||
    Constants?.manifest2?.extra?.expoGo?.debuggerHost ||
    Constants?.manifest?.debuggerHost ||
    "";
  const host = String(hostUri).split(":")[0];
  if (!host || host === "localhost" || host === "127.0.0.1") {
    return FALLBACK_API_HOST;
  }
  return host;
}

const API_BASE_URL = `http://${resolveApiHost()}:8000`;
const PENDING_EVENTS_KEY = "EOSEWS_PENDING_EVENTS";
const MAX_SYNC_RETRIES = 5;
const BASE_RETRY_DELAY_MS = 15000;
const MAX_RETRY_DELAY_MS = 5 * 60 * 1000;
const REQUEST_TIMEOUT_MS = 30000;

async function request(path, method = "GET", token = "", body = null) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["X-API-Token"] = token;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal
    });
  } catch (err) {
    if (err?.name === "AbortError") {
      throw new Error(`Request timed out after ${REQUEST_TIMEOUT_MS / 1000}s`);
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.error || `Request failed with ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return data;
}

async function readPendingEvents() {
  const raw = await AsyncStorage.getItem(PENDING_EVENTS_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

async function writePendingEvents(items) {
  await AsyncStorage.setItem(PENDING_EVENTS_KEY, JSON.stringify(items));
}

function makeIdempotencyKey() {
  return `evt_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

function withIdempotencyKey(payload) {
  if (payload.idempotency_key) return payload;
  return { ...payload, idempotency_key: makeIdempotencyKey() };
}

function computeNextRetryAt(retries) {
  const expoDelay = BASE_RETRY_DELAY_MS * Math.pow(2, Math.max(0, retries - 1));
  const bounded = Math.min(expoDelay, MAX_RETRY_DELAY_MS);
  return new Date(Date.now() + bounded).toISOString();
}

function upsertQueueItem(queue, item) {
  const existingIndex = queue.findIndex((q) => q.idempotency_key === item.idempotency_key);
  if (existingIndex >= 0) {
    const merged = [...queue];
    merged[existingIndex] = { ...merged[existingIndex], ...item };
    return merged;
  }
  return [...queue, item];
}

export async function login(username, password) {
  return request("/api/auth/login", "POST", "", { username, password });
}

export async function getSummary(token) {
  return request("/api/summary", "GET", token);
}

export async function getFlaggedEvents(token, limit = 20, status = "flagged") {
  const safeStatus = encodeURIComponent(status || "flagged");
  return request(`/api/events/flags?limit=${encodeURIComponent(limit)}&status=${safeStatus}`, "GET", token);
}

export async function getFlaggedEventsSummary(token) {
  return request("/api/events/flags/summary", "GET", token);
}

export async function updateEventValidationStatus(token, eventId, status, note = "") {
  return request(`/api/events/${eventId}/validation-status`, "PATCH", token, { status, note });
}

export async function submitUssdReport(token, payload) {
  return request("/api/ussd/report", "POST", token, payload);
}

export async function submitEvent(token, payload) {
  const enriched = withIdempotencyKey(payload);
  try {
    const result = await request("/api/events", "POST", token, enriched);
    return { ...result, sync_status: "synced" };
  } catch (error) {
    // Only queue transient failures (network/timeout/5xx). Validation/auth errors should surface immediately.
    if (typeof error?.status === "number" && error.status >= 400 && error.status < 500) {
      throw error;
    }
    const pending = await readPendingEvents();
    const item = {
      idempotency_key: enriched.idempotency_key,
      payload: enriched,
      created_at: new Date().toISOString(),
      retries: 0,
      last_error: error.message,
      last_attempt_at: new Date().toISOString(),
      next_retry_at: computeNextRetryAt(1),
      status: "pending"
    };
    await writePendingEvents(upsertQueueItem(pending, item));
    return {
      sync_status: "pending",
      idempotency_key: enriched.idempotency_key,
      queued: true
    };
  }
}

export async function syncPendingEvents(token) {
  const pending = await readPendingEvents();
  if (!pending.length) {
    return { synced: 0, failed: 0, pending: 0 };
  }

  try {
    const networkState = await Network.getNetworkStateAsync();
    if (!networkState?.isConnected || networkState?.isInternetReachable === false) {
      const failed = pending.filter((item) => item.status === "failed").length;
      return { synced: 0, failed, pending: pending.length };
    }
  } catch {
    // If network state probing fails, continue with best-effort sync attempts.
  }

  const nextQueue = [];
  let synced = 0;
  let failed = 0;

  for (const item of pending) {
    if (item.status === "failed") {
      nextQueue.push(item);
      failed += 1;
      continue;
    }
    if (item.next_retry_at && Date.parse(item.next_retry_at) > Date.now()) {
      nextQueue.push(item);
      continue;
    }
    try {
      await request("/api/events", "POST", token, item.payload);
      synced += 1;
    } catch (error) {
      const retries = Number(item.retries || 0) + 1;
      if (retries >= MAX_SYNC_RETRIES) {
        nextQueue.push({
          ...item,
          retries,
          status: "failed",
          last_error: error.message,
          last_attempt_at: new Date().toISOString()
        });
        failed += 1;
      } else {
        nextQueue.push({
          ...item,
          retries,
          status: "pending",
          last_error: error.message,
          last_attempt_at: new Date().toISOString(),
          next_retry_at: computeNextRetryAt(retries + 1)
        });
      }
    }
  }

  await writePendingEvents(nextQueue);
  return {
    synced,
    failed,
    pending: nextQueue.length
  };
}

export async function getPendingEventCounts() {
  const pending = await readPendingEvents();
  const counts = { pending: 0, failed: 0 };
  for (const item of pending) {
    if (item.status === "failed") {
      counts.failed += 1;
    } else {
      counts.pending += 1;
    }
  }
  return counts;
}
