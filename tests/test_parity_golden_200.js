/**
 * Golden-file parity test runner:
 * Evaluates all 200 samples in tests/golden_200_scores.json with SentiCallRiskEngine (JS)
 * and verifies that JS probability matches Python within 0.01 tolerance.
 */

const fs = require('fs');
const path = require('path');
const SentiCallRiskEngine = require('../frontend/live_risk_engine');

function runParityTest() {
  const modelPath = path.join(__dirname, '..', 'models', 'text_model.json');
  const tacticsPath = path.join(__dirname, '..', 'data', 'tactics.json');
  const goldenPath = path.join(__dirname, 'golden_200_scores.json');

  console.log('Loading text model, tactics, and golden scores...');
  const modelData = JSON.parse(fs.readFileSync(modelPath, 'utf8'));
  const tacticsData = JSON.parse(fs.readFileSync(tacticsPath, 'utf8'));
  const goldenScores = JSON.parse(fs.readFileSync(goldenPath, 'utf8'));

  const engine = new SentiCallRiskEngine(modelData, tacticsData);

  console.log(`Running parity evaluation across ${goldenScores.length} golden samples...`);
  let maxDiff = 0.0;
  let passedCount = 0;
  let failures = [];

  goldenScores.forEach((sample, idx) => {
    const text = sample.text;
    const pyProb = sample.probability;
    const pyRisk = sample.risk_score;

    const jsAnalysis = engine.analyzeText(text);
    const jsProb = jsAnalysis.probability;
    const jsRisk = jsAnalysis.text_risk_score;

    const diff = Math.abs(pyProb - jsProb);
    if (diff > maxDiff) maxDiff = diff;

    if (diff <= 0.01) {
      passedCount++;
    } else {
      failures.push({
        id: sample.id,
        text: text.substring(0, 60),
        pyProb,
        jsProb,
        diff
      });
    }
  });

  console.log('----------------------------------------------------');
  console.log(`Total samples: ${goldenScores.length}`);
  console.log(`Passed (diff <= 0.01): ${passedCount} / ${goldenScores.length}`);
  console.log(`Max difference observed: ${maxDiff.toFixed(6)}`);

  if (failures.length > 0) {
    console.error('FAILURES:');
    console.error(failures.slice(0, 5));
    process.exit(1);
  } else {
    console.log('SUCCESS: All 200 golden samples matched within 0.01 tolerance!');
    process.exit(0);
  }
}

runParityTest();
