#!/usr/bin/env node
// validate-blackboard.mjs — Validate blackboard JSON files against their JSON schemas

import { execSync } from 'child_process';
import { existsSync, readdirSync } from 'fs';
import { join, basename, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO = join(__dirname, '..');
const SCHEMAS = join(REPO, 'ftm-state', 'schemas');
const BLACKBOARD = join(REPO, 'ftm-state', 'blackboard');

// ---------------------------------------------------------------------------
// Schema-to-data pairs (fixed mappings)
// ---------------------------------------------------------------------------

const FIXED_PAIRS = [
  {
    schema: join(SCHEMAS, 'context.schema.json'),
    data: join(BLACKBOARD, 'context.json'),
    label: 'context',
  },
  {
    schema: join(SCHEMAS, 'experience-index.schema.json'),
    data: join(BLACKBOARD, 'experiences', 'index.json'),
    label: 'experience index',
  },
  {
    schema: join(SCHEMAS, 'patterns.schema.json'),
    data: join(BLACKBOARD, 'patterns.json'),
    label: 'patterns',
  },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Run ajv validate for a single schema/data pair.
 * Returns { passed: boolean, output: string }.
 */
function ajvValidate(schemaPath, dataPath) {
  const cmd = `npx ajv validate -s "${schemaPath}" -d "${dataPath}" --errors=text --validate-formats=false 2>&1`;
  try {
    const output = execSync(cmd, { cwd: REPO, encoding: 'utf8' });
    return { passed: true, output: output.trim() };
  } catch (err) {
    const output = (err.stdout || '') + (err.stderr || '');
    return { passed: false, output: output.trim() };
  }
}

/**
 * Find individual experience files (*.json) in blackboard/experiences/,
 * excluding index.json.
 */
function findExperienceFiles() {
  const dir = join(BLACKBOARD, 'experiences');
  if (!existsSync(dir)) return [];

  return readdirSync(dir)
    .filter((f) => f.endsWith('.json') && f !== 'index.json')
    .map((f) => join(dir, f));
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

const results = [];

// 1. Validate fixed schema/data pairs
for (const { schema, data, label } of FIXED_PAIRS) {
  if (!existsSync(schema)) {
    results.push({ label, passed: false, output: `Schema not found: ${schema}` });
    continue;
  }
  if (!existsSync(data)) {
    results.push({ label, passed: false, output: `Data file not found: ${data}` });
    continue;
  }

  const { passed, output } = ajvValidate(schema, data);
  results.push({ label, passed, output });
}

// 2. Validate individual experience files against experience.schema.json
const experienceSchema = join(SCHEMAS, 'experience.schema.json');
const experienceFiles = findExperienceFiles();

if (experienceFiles.length === 0) {
  results.push({
    label: 'individual experiences',
    passed: true,
    output: 'No individual experience files found — skipped',
  });
} else {
  for (const file of experienceFiles) {
    const label = `experience/${basename(file)}`;
    if (!existsSync(experienceSchema)) {
      results.push({ label, passed: false, output: `Schema not found: ${experienceSchema}` });
      continue;
    }
    const { passed, output } = ajvValidate(experienceSchema, file);
    results.push({ label, passed, output });
  }
}

// ---------------------------------------------------------------------------
// Report
// ---------------------------------------------------------------------------

console.log('');
console.log('Blackboard Validation');
console.log('=====================');

let failCount = 0;

for (const { label, passed, output } of results) {
  if (passed) {
    console.log(`  PASS  ${label}`);
  } else {
    console.log(`  FAIL  ${label}`);
    if (output) {
      for (const line of output.split('\n')) {
        console.log(`        ${line}`);
      }
    }
    failCount++;
  }
}

console.log('');

if (failCount > 0) {
  console.log(`Result: FAIL (${failCount} error(s))`);
  process.exit(1);
}

console.log(`Result: PASS (${results.length} check(s) passed)`);
process.exit(0);
