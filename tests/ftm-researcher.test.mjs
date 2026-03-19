// tests/ftm-researcher.test.mjs
import { readFileSync } from 'fs';
import { test, describe } from 'node:test';
import assert from 'node:assert';

describe('ftm-researcher manifest integration', () => {
  const manifest = JSON.parse(readFileSync('ftm-manifest.json', 'utf8'));
  const skill = manifest.skills.find(s => s.name === 'ftm-researcher');

  test('skill exists in manifest', () => {
    assert.ok(skill, 'ftm-researcher not found in manifest');
  });

  test('emits research_complete event', () => {
    assert.ok(
      skill.events_emits.includes('research_complete'),
      'missing research_complete event'
    );
  });

  test('emits task_completed event', () => {
    assert.ok(
      skill.events_emits.includes('task_completed'),
      'missing task_completed event'
    );
  });

  test('listens to task_received', () => {
    assert.ok(
      skill.events_listens.includes('task_received'),
      'missing task_received listener'
    );
  });

  test('has required references', () => {
    const requiredRefs = [
      'agent-prompts.md',
      'synthesis-pipeline.md',
      'adaptive-search.md',
      'output-format.md',
      'council-integration.md'
    ];
    for (const ref of requiredRefs) {
      assert.ok(
        skill.references.some(r => r.includes(ref)),
        `missing reference: ${ref}`
      );
    }
  });

  test('skill is enabled in config', () => {
    assert.strictEqual(skill.enabled, true);
  });
});

describe('credibility scoring script', () => {
  test('scores a valid finding', async () => {
    const { execSync } = await import('child_process');
    const input = JSON.stringify([{
      claim: "Test claim",
      source_url: "https://arxiv.org/2026/test",
      source_type: "peer_reviewed",
      confidence: 0.8,
      agent_role: "academic_scout",
      evidence: "Test evidence with however some caveats"
    }]);

    const tmpFile = '/tmp/test_scoring_input.json';
    const { writeFileSync } = await import('fs');
    writeFileSync(tmpFile, input);

    const result = execSync(`python3 ftm-researcher/scripts/score_credibility.py ${tmpFile}`);
    const scored = JSON.parse(result.toString());

    assert.strictEqual(scored.length, 1);
    assert.ok(scored[0].credibility_score > 0.7, 'peer_reviewed arxiv should score high');
    assert.strictEqual(scored[0].trust_level, 'high');
    assert.ok(scored[0].score_breakdown);
  });
});

describe('research validation script', () => {
  test('validates a minimal valid output', async () => {
    const { execSync } = await import('child_process');
    const { writeFileSync } = await import('fs');

    const output = {
      mode: "quick",
      findings: [
        { claim: "A", source_type: "blog", confidence: 0.5, agent_role: "web_surveyor", source_url: "https://example.com" },
        { claim: "B", source_type: "code_repo", confidence: 0.7, agent_role: "github_miner", source_url: "https://github.com/test" },
        { claim: "C", source_type: "peer_reviewed", confidence: 0.9, agent_role: "academic_scout", source_url: "https://arxiv.org/test" }
      ],
      disagreement_map: {}
    };

    const tmpFile = '/tmp/test_validation_input.json';
    writeFileSync(tmpFile, JSON.stringify(output));

    const result = execSync(`python3 ftm-researcher/scripts/validate_research.py ${tmpFile}`);
    const validation = JSON.parse(result.toString());

    assert.strictEqual(validation.valid, true);
  });

  test('rejects findings with missing fields', async () => {
    const { execSync } = await import('child_process');
    const { writeFileSync } = await import('fs');

    const output = {
      mode: "quick",
      findings: [
        { claim: "A" }  // missing required fields
      ],
      disagreement_map: {}
    };

    const tmpFile = '/tmp/test_validation_bad.json';
    writeFileSync(tmpFile, JSON.stringify(output));

    try {
      execSync(`python3 ftm-researcher/scripts/validate_research.py ${tmpFile}`);
      assert.fail('Should have exited with error');
    } catch (e) {
      const validation = JSON.parse(e.stdout.toString());
      assert.strictEqual(validation.valid, false);
      assert.ok(validation.errors.length > 0);
    }
  });
});
