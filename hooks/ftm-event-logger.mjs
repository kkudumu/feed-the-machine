#!/usr/bin/env node

/**
 * FTM Event Logger — PostToolUse hook
 * Appends structured JSONL entries to ~/.claude/ftm-state/events.log
 * Debounced: fires every 3rd tool use to avoid overhead
 */

import { readFileSync, appendFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';

const HOME = homedir();
const STATE_DIR = join(HOME, '.claude', 'ftm-state');
const LOG_PATH = join(STATE_DIR, 'events.log');
const COUNTER_PATH = join(STATE_DIR, '.event-counter');
const ARCHIVE_DIR = join(STATE_DIR, 'event-archives');
const MAX_AGE_DAYS = 30;

// Ensure directories exist
if (!existsSync(STATE_DIR)) mkdirSync(STATE_DIR, { recursive: true });

// Read stdin for hook input
let input = '';
process.stdin.setEncoding('utf-8');
process.stdin.on('data', (chunk) => { input += chunk; });
process.stdin.on('end', () => {
  try {
    const hookData = JSON.parse(input);

    // Debounce: only fire every 3rd tool use
    let counter = 0;
    try {
      counter = parseInt(readFileSync(COUNTER_PATH, 'utf-8').trim(), 10) || 0;
    } catch { /* first run */ }

    counter++;
    writeFileSync(COUNTER_PATH, String(counter));

    if (counter % 3 !== 0) {
      process.exit(0); // Skip this invocation
    }

    // Build log entry
    const entry = {
      timestamp: new Date().toISOString(),
      event_type: 'tool_use',
      tool_name: hookData.tool_name || 'unknown',
      tool_input_keys: hookData.tool_input ? Object.keys(hookData.tool_input) : [],
      session_id: process.env.CLAUDE_SESSION_ID || 'unknown',
      skill_context: detectSkillContext(hookData),
    };

    // Append JSONL
    appendFileSync(LOG_PATH, JSON.stringify(entry) + '\n');

    // Log rotation: check once per 100 writes
    if (counter % 100 === 0) {
      rotateOldEntries();
    }

  } catch (e) {
    // Never crash — logging failure should not block execution
    process.exit(0);
  }
});

function detectSkillContext(hookData) {
  const toolName = hookData.tool_name || '';
  if (toolName === 'Skill') return hookData.tool_input?.skill || 'unknown-skill';
  if (toolName === 'Agent') return 'agent-dispatch';
  return null;
}

function rotateOldEntries() {
  try {
    if (!existsSync(LOG_PATH)) return;

    const lines = readFileSync(LOG_PATH, 'utf-8').split('\n').filter(Boolean);
    const cutoff = Date.now() - (MAX_AGE_DAYS * 24 * 60 * 60 * 1000);

    const recent = [];
    const archived = [];

    for (const line of lines) {
      try {
        const entry = JSON.parse(line);
        if (new Date(entry.timestamp).getTime() > cutoff) {
          recent.push(line);
        } else {
          archived.push(line);
        }
      } catch {
        recent.push(line); // Keep unparseable lines
      }
    }

    if (archived.length > 0) {
      if (!existsSync(ARCHIVE_DIR)) mkdirSync(ARCHIVE_DIR, { recursive: true });
      const archivePath = join(ARCHIVE_DIR, `events-${new Date().toISOString().slice(0, 10)}.log`);
      appendFileSync(archivePath, archived.join('\n') + '\n');
      writeFileSync(LOG_PATH, recent.join('\n') + (recent.length > 0 ? '\n' : ''));
    }
  } catch {
    // Rotation failure is non-critical
  }
}
