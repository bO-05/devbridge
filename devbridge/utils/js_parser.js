#!/usr/bin/env node
const fs = require('fs');
const parser = require('@babel/parser');

if (process.argv.length < 3) {
  console.error('Usage: node js_parser.js <file.js>');
  process.exit(1);
}

const filePath = process.argv[2];
const code = fs.readFileSync(filePath, 'utf8');
const lines = code.split(/\r?\n/);

let elements = [];

function getSnippet(start, end) {
  return lines.slice(start - 1, end).join('\n');
}

function walk(node, parent) {
  if (!node || typeof node !== 'object') return;
  // Function Declarations
  if (node.type === 'FunctionDeclaration') {
    elements.push({
      type: 'function_js_ts',
      name: node.id ? node.id.name : '',
      start_line: node.loc.start.line,
      end_line: node.loc.end.line,
      snippet: getSnippet(node.loc.start.line, node.loc.end.line)
    });
  }
  // Class Declarations
  if (node.type === 'ClassDeclaration') {
    elements.push({
      type: 'class_js_ts',
      name: node.id ? node.id.name : '',
      start_line: node.loc.start.line,
      end_line: node.loc.end.line,
      snippet: getSnippet(node.loc.start.line, node.loc.end.line)
    });
  }
  // Variable Declarations (arrow functions, function expressions)
  if (node.type === 'VariableDeclaration') {
    node.declarations.forEach(decl => {
      if (decl.init && (decl.init.type === 'ArrowFunctionExpression' || decl.init.type === 'FunctionExpression')) {
        elements.push({
          type: 'function_js_ts',
          name: decl.id.name,
          start_line: decl.init.loc.start.line,
          end_line: decl.init.loc.end.line,
          snippet: getSnippet(decl.init.loc.start.line, decl.init.loc.end.line)
        });
      }
    });
  }
  // Recurse
  for (let key in node) {
    if (key === 'loc' || key === 'start' || key === 'end') continue;
    const child = node[key];
    if (Array.isArray(child)) {
      child.forEach(c => walk(c, node));
    } else {
      walk(child, node);
    }
  }
}

const ast = parser.parse(code, {
  sourceType: 'module',
  plugins: ['jsx', 'typescript'],
  errorRecovery: true,
  allowReturnOutsideFunction: true,
  allowSuperOutsideMethod: true
});

walk(ast, null);

console.log(JSON.stringify(elements, null, 2)); 