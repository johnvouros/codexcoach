#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const src = path.join(root, "src");
const existingPythonPath = process.env.PYTHONPATH;
const env = {
  ...process.env,
  PYTHONPATH: existingPythonPath ? `${src}${path.delimiter}${existingPythonPath}` : src,
};

function run(candidate) {
  const result = spawnSync(candidate.command, candidate.args.concat(["-m", "codex_coach.cli"], process.argv.slice(2)), {
    stdio: "inherit",
    env,
    windowsHide: false,
  });
  if (result.error) {
    return { ok: false, error: result.error };
  }
  process.exit(result.status === null ? 1 : result.status);
}

const configuredPython = process.env.PYTHON;
const candidates = configuredPython
  ? [{ command: configuredPython, args: [] }]
  : process.platform === "win32"
    ? [
        { command: "py", args: ["-3"] },
        { command: "python", args: [] },
        { command: "python3", args: [] },
      ]
    : [
        { command: "python3", args: [] },
        { command: "python", args: [] },
      ];

const errors = [];
for (const candidate of candidates) {
  const result = run(candidate);
  if (!result.ok) {
    errors.push(`${candidate.command}: ${result.error.message}`);
  }
}

console.error("codex-coach requires Python 3.10+ on PATH.");
if (errors.length) {
  console.error(errors.join("\n"));
}
process.exit(1);
