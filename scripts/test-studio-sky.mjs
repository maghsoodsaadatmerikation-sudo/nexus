import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import Astronomy from '../web/vendor/astronomy-2.1.19.min.js';
globalThis.Astronomy=Astronomy;
await import('../web/studio-astrology.js');await import('../web/studio-sky.js');await import('../web/studio-core.js');
const A=NexusAstrology,K=NexusSky,S=NexusStudio;let checks=0;
const ok=fn=>{fn();checks++};let network=0;globalThis.fetch=()=>{network++;throw Error('network-disabled')};
const vendor=readFileSync(new URL('../web/vendor/astronomy-2.1.19.min.js',import.meta.url));
ok(()=>assert.equal(createHash('sha256').update(vendor).digest('hex'),'f41139a87941ea017ab902b954c9389fa27ea72083d7fab4971756d7769d14e6'));
for(const file of ['j2000','transit']){
 const raw=JSON.parse(readFileSync(new URL('../tests/fixtures/astrology/on-line-astrology-'+file+'.json',import.meta.url))),sky=K.snapshot(raw.input.datetime_utc);
 ok(()=>assert.equal(sky.positions.length,10));ok(()=>assert.equal(sky.acquisition,'computed'));ok(()=>assert.equal(sky.provider,K.VERSION));
 for(const point of sky.positions){ok(()=>assert(A.separation(point.longitude,raw.record.bodies[point.body].longitude)<.01));ok(()=>assert(Math.abs(point.speed-raw.record.bodies[point.body].speed_longitude)<.001))}
}
const jpl=JSON.parse(readFileSync(new URL('../tests/fixtures/astrology/jpl-sun-j2000-reference.json',import.meta.url)));ok(()=>assert(A.separation(K.snapshot('2000-01-01T12:00:00Z').positions[0].longitude,jpl.longitude)<.001));
const now=Date.parse('2026-11-13T12:02:34Z'),sky=K.current(now);ok(()=>assert.equal(sky.at,'2026-11-13T12:00:00Z'));sky.positions[0].longitude=0;ok(()=>assert.notEqual(K.current(now).positions[0].longitude,0));
const original=K.snapshot('2026-11-13T12:00:00Z');
function crafted(moon){const v=structuredClone(original);for(const [body,longitude] of Object.entries({Mo:moon,Ma:0,Sa:40,Ve:80,Ju:155}))v.positions.find(p=>p.body===body).longitude=longitude;return v}
for(const [moon,mode] of [[15,'encouraging'],[45,'practical'],[75,'clear'],[105,'warm']])ok(()=>assert.equal(K.style(crafted(moon)).mode,mode));
const hard=crafted(45);hard.positions.find(p=>p.body==='Ma').longitude=130;ok(()=>assert.equal(K.style(hard).mode,'calm'));
const off=K.presentation({enabled:false,now});ok(()=>assert.equal(off.mode,'neutral'));ok(()=>assert.equal(off.instruction,null));
const instruction=K.presentation({now}).instruction;ok(()=>assert(instruction.includes('Preserve the answer’s facts')));ok(()=>assert(instruction.includes('explicit tone')));ok(()=>assert(instruction.includes('Be candid')));ok(()=>assert(!/astrolog|natal|Saturn|Moon|birth/i.test(instruction)));
for(const fa of [false,true]){const base=S.guide('SYNTHETIC QUESTION',fa,{skyTone:false,now}),styled=S.guide('SYNTHETIC QUESTION',fa,{skyTone:true,now});ok(()=>assert(styled.endsWith(base)));ok(()=>assert(styled.length>base.length));ok(()=>assert(!/astrolog|آسمان|ترنزیت/.test(styled)))}
const project=S.project('No birth profile'),thread=S.append(S.thread('General chat'),'user','Explain a topic','human');project.threads=[thread];
const context=S.context(project,thread,{skyTone:true});ok(()=>assert(context.presentation.engine===K.VERSION));ok(()=>assert(!JSON.stringify(context.messages).includes('natal_positions')));ok(()=>assert(!JSON.stringify(context.messages).includes('longitude')));ok(()=>assert(S.context(project,thread,{skyTone:false}).presentation.mode==='neutral'));
const personal={schema:'nexus.astrology.v1',orb:2,natal:K.snapshot('2000-01-01T12:00:00Z'),transit:K.snapshot('2026-11-13T12:00:00Z')};project.astrology=personal;
ok(()=>assert.equal(S.state({schema:S.SCHEMA,projects:[project]}).projects[0].astrology.natal.acquisition,'computed'));
ok(()=>assert.equal(A.context(personal,{historical:true}).sources.natal,K.VERSION));ok(()=>assert(!JSON.stringify(S.context(project,thread)).includes('2000-01-01T12:00:00Z')));
const actual=globalThis.Astronomy;globalThis.Astronomy=undefined;const missing=K.presentation({now:Date.parse('2028-01-01T00:00:00Z')});ok(()=>assert.equal(missing.mode,'neutral'));globalThis.Astronomy=actual;
ok(()=>assert.throws(()=>K.snapshot('2000-01-01T12:00')));ok(()=>assert.throws(()=>K.current(NaN)));ok(()=>assert.equal(network,0));
console.log(JSON.stringify({status:'PASS',checks,network_requests:network,ephemeris:'actual bundled engine',comparison:'20 source-reference positions and one JPL Sun point; not full-range certification'}));
