'use strict';
const path = require('path');

const LANG = {
  '.sv':'SystemVerilog','.svh':'SystemVerilog','.v':'Verilog','.vh':'Verilog',
  '.py':'Python','.pl':'Perl','.pm':'Perl','.tcl':'Tcl','.sh':'Shell','.bash':'Shell',
  '.js':'JavaScript','.mjs':'JavaScript','.cjs':'JavaScript','.ts':'TypeScript','.tsx':'TypeScript',
  '.c':'C','.h':'C/C++','.cc':'C++','.cpp':'C++','.cxx':'C++','.hpp':'C++',
  '.rs':'Rust','.java':'Java','.go':'Go','.yaml':'YAML','.yml':'YAML','.json':'JSON','.xml':'XML','.toml':'TOML','.md':'Markdown'
};
function languageFor(p){ if(!p) return null; const b=path.basename(p).toLowerCase(); if(b==='makefile') return 'Make'; return LANG[path.extname(b)]||null; }
function uniq(a){ return [...new Set(a.filter(Boolean))]; }
function extractSymbols(text, lang){
  if(!text) return [];
  const s=String(text), out=[]; let m;
  const add=(type,name)=>{ if(name && !out.some(x=>x.type===type&&x.name===name)) out.push({type,name}); };
  const rules=[];
  if(lang==='SystemVerilog'||lang==='Verilog') rules.push(['class',/\bclass\s+([A-Za-z_]\w*)/g],['module',/\bmodule\s+([A-Za-z_]\w*)/g],['interface',/\binterface\s+([A-Za-z_]\w*)/g],['package',/\bpackage\s+([A-Za-z_]\w*)/g],['function',/\bfunction(?:\s+automatic)?(?:\s+[\w:]+)?\s+([A-Za-z_]\w*)\s*\(/g],['task',/\btask(?:\s+automatic)?\s+([A-Za-z_]\w*)\s*\(/g]);
  else if(lang==='Python') rules.push(['class',/^\s*class\s+([A-Za-z_]\w*)/gm],['function',/^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(/gm]);
  else if(['JavaScript','TypeScript'].includes(lang)) rules.push(['class',/\bclass\s+([A-Za-z_$][\w$]*)/g],['function',/\bfunction\s+([A-Za-z_$][\w$]*)\s*\(/g],['function',/\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>/g]);
  else if(['C','C++'].includes(lang)) rules.push(['type',/\b(?:class|struct|enum)\s+([A-Za-z_]\w*)/g],['function',/\b[A-Za-z_]\w*(?:::\w+)?\s+([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{/g]);
  else if(lang==='Rust') rules.push(['type',/\b(?:struct|enum|trait)\s+([A-Za-z_]\w*)/g],['function',/\bfn\s+([A-Za-z_]\w*)\s*\(/g]);
  else if(lang==='Perl') rules.push(['function',/\bsub\s+([A-Za-z_]\w*)/g]);
  else if(lang==='Tcl') rules.push(['proc',/\bproc\s+([^\s{]+)/g]);
  for(const [type,re] of rules){ re.lastIndex=0; while((m=re.exec(s))) add(type,m[1]); }
  return out.slice(0,200);
}
function extractDependencies(text, lang){
  if(!text) return []; const s=String(text), out=[]; let m;
  const rules=[];
  if(lang==='SystemVerilog'||lang==='Verilog') rules.push(/`include\s+"([^"]+)"/g,/\bimport\s+([\w:.*]+)\s*;/g);
  else if(lang==='Python') rules.push(/^\s*from\s+([\w.]+)\s+import/gm,/^\s*import\s+([\w., ]+)/gm);
  else if(['JavaScript','TypeScript'].includes(lang)) rules.push(/(?:from\s+|require\s*\(\s*)['"]([^'"]+)['"]/g);
  else if(['C','C++'].includes(lang)) rules.push(/#include\s*[<"]([^>"]+)[>"]/g);
  else if(lang==='Rust') rules.push(/\buse\s+([^;]+);/g);
  for(const re of rules){ re.lastIndex=0; while((m=re.exec(s))) out.push(m[1].trim()); }
  return uniq(out).slice(0,200);
}
function classifyChange(event){
  if(event.op==='view') return 'inspection'; if(event.op==='create') return 'creation'; if(event.op==='delete') return 'deletion'; if(event.op==='rename') return 'refactor/move'; if(event.op==='bash') return 'command';
  const d=String(event.detail||'').toLowerCase(); if(/test|assert|coverage|scoreboard|sequence/.test(d)) return 'verification/test-change'; if(/config|yaml|json|toml|makefile/.test(String(event.path||'').toLowerCase())) return 'configuration-change'; return event.op==='edit'?'logic-change':'other';
}
function detectTestCommand(command=''){
  const c=String(command); const patterns=[['pytest',/\bpytest\b/i],['npm-test',/\bnpm\s+test\b/i],['cargo-test',/\bcargo\s+test\b/i],['make',/\bmake\b/i],['vcs',/\bvcs\b/i],['xrun',/\bxrun\b/i],['questa',/\b(?:vsim|questa)\b/i],['trs',/\btrs\s+rt\b/i]];
  for(const [kind,re] of patterns) if(re.test(c)) return kind; return null;
}
function detectTestOutcome(result, detail=''){
  const s = `${typeof result==='string'?result:JSON.stringify(result||'')} ${detail||''}`.toLowerCase();
  if(!s.trim()) return null;
  if(/\b(pass(?:ed)?|success|successful|0 failed|test_passed|uvm_none)\b/.test(s) && !/\b(fail(?:ed|ure)?|error|fatal|test_failed|uvm_error|uvm_fatal)\b/.test(s)) return 'PASS';
  if(/\b(fail(?:ed|ure)?|test_failed|uvm_error|uvm_fatal|fatal|assertion failed)\b/.test(s)) return 'FAIL';
  if(/\b(timeout|timed out)\b/.test(s)) return 'TIMEOUT';
  return null;
}
function enrichEvent(event){
  const language=languageFor(event.path); const symbols=extractSymbols(event.detail,language); const dependencies=extractDependencies(event.detail,language); const changeType=classifyChange(event); const testKind=event.op==='bash'?detectTestCommand(event.summary||event.detail):null; const testOutcome=testKind?detectTestOutcome(event.result,event.detail):null;
  return { language, symbols, dependencies, changeType, testKind, testOutcome };
}
module.exports={languageFor,extractSymbols,extractDependencies,classifyChange,detectTestCommand,detectTestOutcome,enrichEvent};
