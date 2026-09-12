#!/usr/bin/env node
'use strict';
const fs=require('fs'),os=require('os'),path=require('path'),cp=require('child_process');
const cli=path.join(__dirname,'cli.js'),L=require('./lib/ledger');
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'session-ledger-v3-'));process.env.LEDGER_HOME=path.join(tmp,'home');const work=path.join(tmp,'work');fs.mkdirSync(work,{recursive:true});
function run(args,env={}){return cp.execFileSync(process.execPath,[cli,...args],{encoding:'utf8',env:{...process.env,NODE_NO_WARNINGS:'1',...env}}).trim();}
function ok(x,m){if(!x)throw new Error(m);}function expectThrow(fn,m){let hit=false;try{fn();}catch(_){hit=true;}ok(hit,m);}
const sid=run(['start-session','--client','test','--cwd',work]);
const f=path.join(work,'x.sv');fs.writeFileSync(f,'`include "defs.svh"\nclass c; function void f(); endfunction endclass\n');
run(['log','--session',sid,'--op','edit','--tool','Edit','--path',f,'--summary','edit reset logic','--detail','`include "defs.svh"\nclass c; function void f(); endfunction endclass']);
let ev=L.loadSessionEvents(sid);L.verifyChain(ev);ok(ev[0].language==='SystemVerilog','language');ok(ev[0].symbols.some(s=>s.name==='f'),'symbol');ok(ev[0].dependencies.includes('defs.svh'),'dependency');
run(['log','--session',sid,'--op','bash','--tool','Bash','--path',work,'--summary','pytest -q','--detail','api_key=abcdefghijklmnopqrstuv','--result','FAILED assertion failed']);
ev=L.loadSessionEvents(sid);ok(ev[1].testKind==='pytest'&&ev[1].testOutcome==='FAIL','failure classification');ok(!fs.readFileSync(path.join(L.sessionDir(sid),'events.jsonl'),'utf8').includes('abcdefghijklmnopqrstuv'),'secret redaction');
run(['log','--session',sid,'--op','edit','--tool','Edit','--path',f,'--summary','fix failing test','--detail','function void f(); /* fixed */ endfunction']);
run(['log','--session',sid,'--op','bash','--tool','Bash','--path',work,'--summary','pytest -q','--result','1 passed']);
ok(L.buildCorrelations(sid).length===1,'FAIL-change-PASS correlation');
const graph=L.buildDependencyGraph(sid);ok(graph.edges.some(e=>e.to==='defs.svh'),'dependency graph');
const cpj=JSON.parse(run(['checkpoint','--session',sid,'--path',f]));fs.writeFileSync(f,'bad');run(['restore',cpj.id,'--session',sid]);ok(fs.readFileSync(f,'utf8').includes('class c'),'restore');
run(['reindex']);ok(JSON.parse(run(['ask','reset logic','--session',sid])).matches.length>0,'ask/search');
const child=run(['start-session','--client','test','--cwd',work,'--parent',sid]);ok(L.sessionTree().some(x=>x.id===sid&&x.children.some(c=>c.id===child)),'parent child tree');run(['end-session','--session',child]);
// concurrent writers
const conc=run(['start-session','--client','test','--cwd',work]);const ps=[];for(let i=0;i<20;i++)ps.push(cp.spawn(process.execPath,[cli,'log','--session',conc,'--op','bash','--tool','Bash','--path',work,'--summary',`echo ${i}`],{env:{...process.env,NODE_NO_WARNINGS:'1'},stdio:'ignore'}));
Promise.all(ps.map(p=>new Promise((resolve,reject)=>p.on('exit',c=>c===0?resolve():reject(new Error('concurrent child failed')))))).then(()=>{
  const ce=L.loadSessionEvents(conc);ok(ce.length===20,'concurrent count');L.verifyChain(ce);run(['end-session','--session',conc]);
  run(['end-session','--session',sid]);ok(L.loadSessionMeta(sid).endedAt,'end');const gz=run(['archive','--session',sid]);ok(fs.existsSync(gz),'archive exists');ok(!fs.existsSync(path.join(L.sessionDir(sid),'events.jsonl')),'source removed after archive');const ae=L.loadSessionEvents(sid);ok(ae.length===4,'read compressed archive');L.repairSession(sid);ok(fs.existsSync(path.join(L.sessionDir(sid),'ledger.json')),'repair archived derived view');
  expectThrow(()=>L.validateSessionId('../escape'),'traversal rejection');
  console.log('PASS session-ledger v3 advanced regression');
}).catch(e=>{console.error(e.stack||e);process.exit(1);});
