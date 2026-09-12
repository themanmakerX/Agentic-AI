#!/usr/bin/env node
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const L = require('../lib/ledger');
function readStdin() { return new Promise((resolve, reject) => { let d=''; process.stdin.setEncoding('utf8'); process.stdin.on('data',c=>d+=c); process.stdin.on('end',()=>resolve(d)); process.stdin.on('error',reject); }); }
function sha256File(p) { try { if (!fs.statSync(p).isFile()) return null; return crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'); } catch (_) { return null; } }
function pendingPath(sessionId, toolUseId) { const safe = crypto.createHash('sha256').update(String(toolUseId || 'unknown')).digest('hex'); return path.join(L.sessionDir(sessionId), 'pending', `${safe}.json`); }
function atomicSmallWrite(p,obj){ fs.mkdirSync(path.dirname(p),{recursive:true}); const tmp=p+`.${process.pid}.tmp`; fs.writeFileSync(tmp,JSON.stringify(obj)); fs.renameSync(tmp,p); }
function readPending(p){ try{return JSON.parse(fs.readFileSync(p,'utf8'));}catch(_){return null;} }
function toolPath(toolName,input,payload){ const n=(toolName||'').toLowerCase(); if(n.includes('notebookedit')) return input.notebook_path||input.path||null; if(n.includes('bash')) return payload.cwd||input.cwd||null; return input.file_path||input.path||input.notebook_path||null; }
function eventKind(payload){ return String(payload.hook_event_name||payload.event_name||payload.event||'').toLowerCase(); }
function isPre(payload){ return eventKind(payload).includes('pretooluse'); }
function linesForRead(input){ if(input.offset === undefined || input.offset === null) return null; const start=Number(input.offset); const limit=input.limit===undefined||input.limit===null?1:Number(input.limit); if(!Number.isInteger(start)||start<0||!Number.isInteger(limit)||limit<0) return null; return {start,end: limit>0 ? start+limit-1 : start}; }
function classify(toolName,input,payload,pending){
  const name=(toolName||'').toLowerCase(); const p=toolPath(toolName,input,payload);
  if(name.includes('notebookedit')) return {op:'edit',path:p,lines:null,summary:'notebook cell edit',detail:JSON.stringify({cell_id:input.cell_id||input.cell_number||null,edit_mode:input.edit_mode||null,new_source:input.new_source||input.new_string||null},null,2),beforeHash:pending&&pending.beforeHash,afterHash:sha256File(p)};
  if(name.includes('write')||name.includes('create_file')) { const existed=pending ? !!pending.existedBefore : null; return {op: existed===false?'create':'edit',path:p,lines:null,summary: existed===false?'created file':existed===true?'overwrote existing file':'wrote file (pre-state unavailable)',detail:input.content||null,beforeHash:pending&&pending.beforeHash,afterHash:sha256File(p)}; }
  if(name.includes('edit')||name.includes('str_replace')) { const oldStr=input.old_string??input.old_str??''; const newStr=input.new_string??input.new_str??''; const oldLines=oldStr?String(oldStr).split('\n').length:null; return {op:'edit',path:p,lines:null,summary:`edited${oldLines?` (${oldLines} line(s) replaced)`:''}`,detail:JSON.stringify({before:oldStr,after:newStr,replace_all:!!input.replace_all},null,2),beforeHash:pending&&pending.beforeHash,afterHash:sha256File(p)}; }
  if(name==='read'||name.includes('view')) return {op:'view',path:p,lines:linesForRead(input),summary:'viewed'};
  if(name.includes('delete')||name.includes('remove_file')) return {op:'delete',path:p,lines:null,summary:'deleted',beforeHash:pending&&pending.beforeHash,afterHash:null};
  if(name.includes('rename')||name.includes('move')) return {op:'rename',fromPath:input.source||input.from||input.old_path||input.file_path||null,path:input.destination||input.to||input.new_path||input.path||null,lines:null,summary:'renamed/moved'};
  if(name==='bash'||name.includes('bash')) return {op:'bash',path:payload.cwd||input.cwd||null,lines:null,summary:String(input.command||'').slice(0,1000),detail:JSON.stringify({command:input.command||'',description:input.description||null,note:'Command-level capture only; filesystem side effects performed inside the shell are not inferred unless the client emits separate file-tool events.'},null,2)};
  return {op:'other',path:p,lines:null,summary:`${toolName||'unknown tool'} call`};
}
(async()=>{
  try{
    const raw=await readStdin(); const payload=JSON.parse(raw||'{}');
    const sessionId=payload.session_id||L.currentSessionId({cwd:payload.cwd,client:'claude-code'})||L.startSession({client:'claude-code',cwd:payload.cwd}).id;
    L.ensureSession(sessionId,{client:'claude-code',cwd:payload.cwd});
    const toolName=payload.tool_name||''; const input=payload.tool_input||{}; const toolUseId=payload.tool_use_id||payload.tool_call_id||`${toolName}:${JSON.stringify(input).slice(0,200)}`; const pp=pendingPath(sessionId,toolUseId); const p=toolPath(toolName,input,payload);
    if(isPre(payload)) {
      const preview=classify(toolName,input,payload,null);
      const cp=L.autoCheckpoint(sessionId,{...preview,summary:preview.summary||String(input.command||'')},p?[p]:[]);
      atomicSmallWrite(pp,{existedBefore:p?fs.existsSync(p):false,beforeHash:p?sha256File(p):null,path:p,ts:new Date().toISOString(),checkpointId:cp&&cp.id||null}); return; }
    const pending=readPending(pp); try{fs.unlinkSync(pp);}catch(_){}
    const mapped=classify(toolName,input,payload,pending);
    if(mapped.op!=='bash' && !mapped.path) throw new Error(`No path could be determined for ${toolName}`);
    const result = payload.tool_result || payload.result || payload.tool_response || null;
    L.logEvent(sessionId,{tool:toolName||'unknown',...mapped,result:result==null?null:(typeof result==='string'?result:JSON.stringify(result).slice(0,4000))});
  }catch(e){ console.error('claude-code-hook error:',e.message); process.exitCode=1; }
})();
