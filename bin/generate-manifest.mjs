#!/usr/bin/env node
/**
 * generate-manifest.mjs
 *
 * Scans all panda skill SKILL.md files and produces panda-manifest.json
 * at the project root with structured metadata for each skill.
 *
 * Usage: node bin/generate-manifest.mjs
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import matter from 'gray-matter';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

// ---------------------------------------------------------------------------
// Discovery — collect all SKILL.md paths
// ---------------------------------------------------------------------------

/**
 * Returns an array of { skillFile, skillDir, triggerFile } objects.
 * Handles both panda-X/SKILL.md pattern and the special panda/SKILL.md root skill.
 */
function discoverSkillFiles() {
  const entries = fs.readdirSync(ROOT, { withFileTypes: true });
  const skills = [];

  for (const entry of entries) {
    if (!entry.isDirectory()) continue;

    const dirName = entry.name;

    // Root panda skill
    if (dirName === 'panda') {
      const skillFile = path.join(ROOT, 'panda', 'SKILL.md');
      if (fs.existsSync(skillFile)) {
        skills.push({
          skillFile,
          skillDir: 'panda/',
          triggerFile: 'panda.yml',
        });
      }
      continue;
    }

    // panda-* skill directories
    if (dirName.startsWith('panda-')) {
      const skillFile = path.join(ROOT, dirName, 'SKILL.md');
      if (fs.existsSync(skillFile)) {
        skills.push({
          skillFile,
          skillDir: `${dirName}/`,
          triggerFile: `${dirName}.yml`,
        });
      }
    }
  }

  return skills;
}

// ---------------------------------------------------------------------------
// Parsing helpers
// ---------------------------------------------------------------------------

/**
 * Splits markdown content into a map of { sectionHeading -> lines[] }.
 * Tracks both ## and ### headings.
 */
function parseSections(content) {
  const lines = content.split('\n');
  const sections = {};
  let currentHeading = null;

  for (const line of lines) {
    const h2Match = line.match(/^##\s+(.+)/);
    const h3Match = line.match(/^###\s+(.+)/);

    if (h2Match) {
      currentHeading = h2Match[1].trim();
      sections[currentHeading] = [];
    } else if (h3Match) {
      currentHeading = h3Match[1].trim();
      sections[currentHeading] = [];
    } else if (currentHeading !== null) {
      sections[currentHeading].push(line);
    }
  }

  return sections;
}

/**
 * Extracts event names from lines under an Emits or Listens To section.
 * Format: - `event_name` — description
 */
function extractEventNames(lines) {
  const events = [];
  const eventRegex = /^-\s*`([^`]+)`/;

  for (const line of lines) {
    const match = line.match(eventRegex);
    if (match) {
      events.push(match[1]);
    }
  }

  return events;
}

/**
 * Extracts ~/.claude/panda-state/... paths from blackboard section lines.
 */
function extractBlackboardPaths(lines) {
  const paths = [];
  // Match backtick-quoted paths containing panda-state
  const pathRegex = /`(~\/.claude\/panda-state\/[^`]+)`/g;

  for (const line of lines) {
    let match;
    while ((match = pathRegex.exec(line)) !== null) {
      if (!paths.includes(match[1])) {
        paths.push(match[1]);
      }
    }
  }

  return paths;
}

// ---------------------------------------------------------------------------
// Per-skill metadata extraction
// ---------------------------------------------------------------------------

function processSkill({ skillFile, skillDir, triggerFile }) {
  const raw = fs.readFileSync(skillFile, 'utf8');
  const stat = fs.statSync(skillFile);
  const parsed = matter(raw);

  const { name, description } = parsed.data;
  const sections = parseSections(parsed.content);

  // Events
  const eventsEmits = extractEventNames(sections['Emits'] || []);
  const eventsListens = extractEventNames(sections['Listens To'] || []);

  // Blackboard paths
  const blackboardReads = extractBlackboardPaths(sections['Blackboard Read'] || []);
  const blackboardWrites = extractBlackboardPaths(sections['Blackboard Write'] || []);

  // References directory
  const referencesDir = path.join(ROOT, skillDir, 'references');
  let references = [];
  if (fs.existsSync(referencesDir)) {
    try {
      references = fs.readdirSync(referencesDir).filter(f => {
        const fullPath = path.join(referencesDir, f);
        return fs.statSync(fullPath).isFile();
      });
    } catch {
      references = [];
    }
  }

  // Evals directory
  const evalsDir = path.join(ROOT, skillDir, 'evals');
  const hasEvals = fs.existsSync(evalsDir) && fs.statSync(evalsDir).isDirectory();

  return {
    name: name || path.basename(skillDir, '/'),
    description: description || '',
    trigger_file: triggerFile,
    skill_directory: skillDir,
    events_emits: eventsEmits,
    events_listens: eventsListens,
    blackboard_reads: blackboardReads,
    blackboard_writes: blackboardWrites,
    references,
    has_evals: hasEvals,
    size_bytes: stat.size,
    enabled: true,
  };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main() {
  const skillEntries = discoverSkillFiles();
  const skills = skillEntries.map(processSkill);

  // Sort alphabetically by name
  skills.sort((a, b) => a.name.localeCompare(b.name));

  const manifest = {
    generated_at: new Date().toISOString(),
    skills,
  };

  const outputPath = path.join(ROOT, 'panda-manifest.json');
  fs.writeFileSync(outputPath, JSON.stringify(manifest, null, 2) + '\n', 'utf8');

  process.stderr.write(`Generated manifest for ${skills.length} skills\n`);
}

main();
