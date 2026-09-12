#!/usr/bin/env node
'use strict';
const L=require('./lib/ledger');
function parseArgs(argv){const o={_:[]};let pos=false;for(let i=0;i<argv.length;i++){const a=argv[i];if(a==='--'){pos=true;continue;}if(!pos&&a.startsWith('--')){const eq=a.indexOf('=');if(eq>2){o[a.slice(2,eq)]=a.slice(eq+1);continue;}const k=a.slice(2),n=argv[i+1];if(['regex','dry-run','commands','files','json'].includes(k)){o[k]=true;continue;}if(n!==undefined){o[k]=n;i++;}else o[k]=true;}else o._.push(a);}return o;}
function lines(s){if(s==null||s==='')return null;const m=String(s).match(/^(\d+)(?::(\d+))?$/);if(!m)throw new Error('--lines must be start or start:end');return L.normalizeLines({start:Number(m[1]),end:m[2]===undefined?Number(m[1]):Number(m[2])});}
function sid(a){return a.session||L.currentSessionId({cwd:process.cwd()})||L.currentSessionId();} function die(m){console.error(m);process.exit(1);} function print(x,json){console.log(json?JSON.stringify(x,null,2):x);}
function main(){try{const[,,cmd,...rest]=process.argv,a=parseArgs(rest);switch(cmd){
case'start-session':{const m=L.startSession({client:a.client,project:a.project,cwd:a.cwd,parentSessionId:a.parent});print(m.id);break;}
case'end-session':{const id=sid(a);if(!id)return die('No session to end.');L.endSession(id);print(`ended ${id}`);break;}
case'log':{const id=sid(a);if(!id)return die('No active session.');if(!a.op||!L.OPS.has(a.op))return die(`--op required: ${[...L.OPS].join(', ')}`);if(!a.tool||a.tool===true)return die('--tool required');if(a.op!=='bash'&&(!a.path||a.path===true))return die('--path required');const e=L.logEvent(id,{op:a.op,tool:a.tool,path:a.path||process.cwd(),fromPath:a['from-path'],lines:lines(a.lines),summary:a.summary===true?'':a.summary,detail:a.detail===true?'':a.detail,parentEventSeq:a.parent?Number(a.parent):null,causedBy:a['caused-by'],result:a.result});print(e,true);break;}
case'show':{const id=sid(a);if(!id)return die('No session found.');print(L.renderMd(L.loadSessionMeta(id),L.loadSessionEvents(id)));break;}
case'list':{for(const[id,s]of Object.entries(L.listSessions()).sort((x,y)=>String(y[1].startedAt).localeCompare(String(x[1].startedAt))))print(`${id}\t${s.project}\t${s.client}\t${s.startedAt}\t${s.endedAt||'(open)'}\tparent=${s.parentSessionId||''}`);break;}
case'search':{const q=a._[0];if(!q)return die('search <text>');const rows=L.searchIndexed(q,{session:a.session,limit:a.limit||50});if(rows.length){for(const r of rows)print(`${r.session_id}#${r.seq}\t${r.ts}\t[${r.op}]\t${r.path||''}\t${r.summary||''}`);break;}let re;if(a.regex)try{re=new RegExp(q,'i');}catch(e){return die(`Invalid regex: ${e.message}`);}const f=a.regex?h=>re.test(h):h=>h.toLowerCase().includes(String(q).toLowerCase());for(const id of a.session?[a.session]:Object.keys(L.listSessions()))for(const e of L.loadSessionEvents(id)){const h=`${e.path||''} ${e.summary||''} ${e.detail||''}`;if(f(h))print(`${id}#${e.seq}\t${e.ts}\t[${e.op}]\t${e.path||''}\t${e.summary||''}`);}break;}
case'ask':{const q=a._.join(' ');if(!q)return die('ask <natural language query>');print(L.ask(q,{session:a.session}),true);break;}
case'summary':{const id=sid(a);if(!id)return die('No session.');print(L.getSummary(id),true);break;}
case'replay':{const id=sid(a);if(!id)return die('No session.');const r=L.replay(id,{commands:a.commands,files:a.files});for(const e of r)print(`${e.ts}\t#${e.seq}\t[${e.op}]\tR${e.risk}\t${e.path||''}\t${e.summary||''}`);break;}
case'graph':{const id=sid(a);if(!id)return die('No session.');print(L.buildDependencyGraph(id),true);break;}
case'tree':{print(L.sessionTree(),true);break;}
case'relations':{const id=sid(a);if(!id)return die('No session.');print(L.getRelations(id),true);break;}
case'correlations':{const id=sid(a);if(!id)return die('No session.');print(L.buildCorrelations(id),true);break;}
case'checkpoint':{const id=sid(a);if(!id)return die('No session.');const ps=a.path?String(a.path).split(','):[];print(L.createCheckpoint(id,{paths:ps,reason:a.reason||'manual'}),true);break;}
case'checkpoints':{const id=sid(a);if(!id)return die('No session.');print(L.listCheckpoints(id),true);break;}
case'restore':{const id=sid(a),cp=a._[0];if(!id||!cp)return die('restore <checkpoint-id> [--session id] [--dry-run]');print(L.restoreCheckpoint(id,cp,{dryRun:!!a['dry-run']}),true);break;}
case'policy':{if(a.set){const p=JSON.parse(a.set);print(L.savePolicy(p),true);}else print(L.loadPolicy(),true);break;}
case'reindex':{print(`sqlite-index=${L.rebuildSearchIndex()?'rebuilt':'unavailable'}`);break;}
case'repair':{if(!a.session)return die('repair requires --session');const e=L.repairSession(a.session);print(`repaired ${a.session} (${e.length} events)`);break;}
case'archive':{const id=sid(a);if(!id)return die('No session.');print(L.archiveSession(id));break;}
case'retention':{print(L.runRetention(),true);break;}
default:print(`session-ledger v3\n\nCommands:\n start-session [--parent id]\n end-session\n log ...\n list | show | summary | replay | graph | tree | relations | correlations\n search <text> | ask <question> | reindex\n checkpoint [--path a,b] | checkpoints | restore <id> [--dry-run]\n policy [--set '{"checkpointRiskAtOrAbove":4}']\n repair --session id | archive | retention\n\nNo Git/GitHub integration is included.`);}}
catch(e){die(`session-ledger: ${e.message}`);}}main();
