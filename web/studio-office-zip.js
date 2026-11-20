/* Bounded ZIP and XML readers reused by Studio and the offline file desk. */
(function(root){'use strict';
function decodeFileText(bytes){
  if(bytes[0]===0xff&&bytes[1]===0xfe)return new TextDecoder('utf-16le',{fatal:true}).decode(bytes.subarray(2));
  if(bytes[0]===0xfe&&bytes[1]===0xff)return new TextDecoder('utf-16be',{fatal:true}).decode(bytes.subarray(2));
  return new TextDecoder('utf-8',{fatal:true}).decode(bytes);
}
function xmlDocument(bytes){
  const text=decodeFileText(bytes);if(/<!DOCTYPE|<!ENTITY/i.test(text))throw Error('xml-dtd');
  const doc=new DOMParser().parseFromString(text,'application/xml');
  if(doc.getElementsByTagName('parsererror').length)throw Error('invalid-xml');return doc;
}
const xmlElements=(node,name)=>Array.from(node.getElementsByTagNameNS('*',name));
const xmlText=(node,name)=>xmlElements(node,name).map(n=>n.textContent).join('');
const ZIP_CRC_TABLE=Uint32Array.from({length:256},(_,value)=>{let c=value;for(let i=0;i<8;i++)c=(c>>>1)^((c&1)?0xedb88320:0);return c>>>0;});
function crc32(bytes){
  let crc=0xffffffff;for(const byte of bytes)crc=(crc>>>8)^ZIP_CRC_TABLE[(crc^byte)&255];
  return (crc^0xffffffff)>>>0;
}
function zipReader(bytes, maxEntryBytes){
  const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength),size=bytes.length;
  const u16=at=>view.getUint16(at,true),u32=at=>view.getUint32(at,true);
  let end=-1;
  for(let at=size-22;at>=Math.max(0,size-65557);at--)if(u32(at)===0x06054b50&&at+22+u16(at+20)===size){end=at;break;}
  if(end<0||u16(end+4)||u16(end+6)||u16(end+8)!==u16(end+10)||u16(end+10)>500||u32(end+16)+u32(end+12)!==end)throw Error('zip-directory');
  const directory=u32(end+16),map=new Map();let at=directory,expanded=0;
  for(let i=0;i<u16(end+10);i++){
    if(at+46>end||u32(at)!==0x02014b50)throw Error('zip-central');
    const n=u16(at+28),extra=u16(at+30),comment=u16(at+32),flags=u16(at+8),method=u16(at+10),packed=u32(at+20),raw=u32(at+24),offset=u32(at+42),crc=u32(at+16);
    if(at+46+n+extra+comment>end||flags&1||u16(at+34))throw Error('zip-entry');
    const name=new TextDecoder('utf-8',{fatal:true}).decode(bytes.subarray(at+46,at+46+n));
    if(!name||name.includes('\\')||name.startsWith('/')||name.split('/').includes('..')||name.includes('\0')||map.has(name))throw Error('zip-path');
    map.set(name,{name,flags,method,packed,raw,offset,crc});at+=46+n+extra+comment;
  }
  if(at!==end)throw Error('zip-directory-size');
  return {names:Array.from(map.keys()),read:async name=>{
    const entry=map.get(name);if(!entry||entry.raw>maxEntryBytes||(expanded+=entry.raw)>3*maxEntryBytes||![0,8].includes(entry.method))throw Error('zip-budget');
    const o=entry.offset;
    if(o+30>directory||u32(o)!==0x04034b50||(u16(o+6)&1)||u16(o+8)!==entry.method)throw Error('zip-local');
    const n=u16(o+26),extra=u16(o+28),start=o+30+n+extra;
    if(start+entry.packed>directory||new TextDecoder('utf-8',{fatal:true}).decode(bytes.subarray(o+30,o+30+n))!==name)throw Error('zip-offset');
    const compressed=bytes.subarray(start,start+entry.packed);let data;
    if(entry.method===0)data=compressed;
    else{
      const stream=new Blob([compressed]).stream().pipeThrough(new DecompressionStream('deflate-raw')).getReader(),parts=[];let length=0;
      try{while(true){const step=await stream.read();if(step.done)break;length+=step.value.length;if(length>entry.raw||length>maxEntryBytes)throw Error('zip-inflation');parts.push(step.value);}}
      catch(error){try{await stream.cancel()}catch{}throw error;}
      data=new Uint8Array(length);let p=0;for(const part of parts){data.set(part,p);p+=part.length;}
    }
    if(data.length!==entry.raw||crc32(data)!==entry.crc)throw Error('zip-integrity');return data;
  }};
}
const DOCX_MAX_BYTES=2*1024*1024;
const WORD_NAMESPACES=[
 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
 'http://purl.oclc.org/ooxml/wordprocessingml/main'
];

async function readDocx(file){
 if(!Number.isSafeInteger(file.size)||file.size<1||file.size>DOCX_MAX_BYTES)throw Error('docx-size');
 const bytes=new Uint8Array(await file.arrayBuffer());
 if(bytes.length!==file.size)throw Error('docx-size');
 const zip=zipReader(bytes,512*1024);
 const document=xmlDocument(await zip.read('word/document.xml'));
 const main=document.documentElement,ns=main.namespaceURI;
 const bodies=Array.from(main.children).filter(node=>node.namespaceURI===ns&&node.localName==='body');
 if(main.localName!=='document'||!WORD_NAMESPACES.includes(ns)||bodies.length!==1)throw Error('docx-document');
 const filter=node=>node.namespaceURI===ns&&['del','moveFrom'].includes(node.localName)
  ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
 const walker=document.createTreeWalker(bodies[0],NodeFilter.SHOW_ELEMENT,filter);
 const parts=[];
 for(let node=walker.nextNode();node;node=walker.nextNode()){
  if(node.namespaceURI!==ns)continue;
  if(node.localName==='p'||node.localName==='br'||node.localName==='cr')parts.push('\n');
  else if(node.localName==='tab')parts.push('\t');
  else if(node.localName==='t'&&!node.children.length)parts.push(node.textContent);
 }
 const text=parts.join('').trim();
 if(!text||new TextEncoder().encode(text).length>131072)throw Error('docx-text');
 return text;
}

root.NexusOfficeZip=Object.freeze({decodeFileText,xmlDocument,xmlElements,xmlText,crc32,zipReader,readDocx,DOCX_MAX_BYTES});
})(globalThis);
