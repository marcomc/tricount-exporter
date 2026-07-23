#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..', 'apps-script');
const files = fs.readdirSync(root).filter((name) => name.endsWith('.gs')).sort();
const failures = [];
for (const file of files) {
  try {
    new Function(fs.readFileSync(path.join(root, file), 'utf8'));
  } catch (error) {
    failures.push(`${file}: ${error.message}`);
  }
}
if (failures.length > 0) {
  console.error(failures.join('\n'));
  process.exit(1);
}
console.log(`Apps Script syntax passed for ${files.length} files.`);
