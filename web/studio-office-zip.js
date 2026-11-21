/* Bounded ZIP and XML helpers for Studio Office documents. */
(function(root){'use strict';
const PREVIEW_LIMIT=512*1024;
// Studio exports a single document without tray attachments.
const TRAY_LIMIT=0;
/* OFFICE_ZIP_HELPERS */
const OFFICE_MAX_BYTES=2*1024*1024;
const WORD_NAMESPACES=[
 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
 'http://purl.oclc.org/ooxml/wordprocessingml/main'
];

async function officeZip(file){
 if(!Number.isSafeInteger(file.size)||file.size<1||file.size>OFFICE_MAX_BYTES)throw Error('office-size');
 const bytes=new Uint8Array(await file.arrayBuffer());
 if(bytes.length!==file.size)throw Error('office-size');
 return zipReader(bytes);
}
const children=(node,ns,name)=>Array.from(node.children).filter(child=>child.namespaceURI===ns&&child.localName===name);
function boundedText(text){
 const result=text.trim();
 if(!result||new TextEncoder().encode(result).length>131072)throw Error('office-text');
 return result;
}
async function readDocx(file){
 const zip=await officeZip(file);
 const document=xmlDocument(await zip.read('word/document.xml'));
 const main=document.documentElement,ns=main.namespaceURI;
 const bodies=children(main,ns,'body');
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
 return boundedText(parts.join(''));
}

const PRESENTATION_NAMESPACES=[
 ['http://schemas.openxmlformats.org/presentationml/2006/main','http://schemas.openxmlformats.org/drawingml/2006/main','http://schemas.openxmlformats.org/officeDocument/2006/relationships'],
 ['http://purl.oclc.org/ooxml/presentationml/main','http://purl.oclc.org/ooxml/drawingml/main','http://purl.oclc.org/ooxml/officeDocument/relationships']
];
const PACKAGE_REL='http://schemas.openxmlformats.org/package/2006/relationships';
const invalidSlide=()=>{throw Error('pptx-structure')};

function slideParts(presentation,rels){
 const definition=PRESENTATION_NAMESPACES.find(([ns])=>ns===presentation.namespaceURI);
 if(!definition||presentation.localName!=='presentation'||rels.namespaceURI!==PACKAGE_REL||rels.localName!=='Relationships')invalidSlide();
 const [ns,drawing,relationship]=definition;
 const lists=children(presentation,ns,'sldIdLst');
 if(lists.length!==1)invalidSlide();
 const ids=children(lists[0],ns,'sldId').map(slide=>slide.getAttributeNS(relationship,'id'));
 if(!ids.length||ids.length>20||ids.some(id=>!id)||new Set(ids).size!==ids.length)invalidSlide();
 const registered=new Map();
 for(const rel of children(rels,PACKAGE_REL,'Relationship')){
  const id=rel.getAttribute('Id');
  if(!id||registered.has(id))invalidSlide();
  registered.set(id,rel);
 }
 const paths=ids.map(id=>{
  const rel=registered.get(id);
  if(!rel||rel.getAttribute('Type')!==relationship+'/slide'||!['','Internal'].includes(rel.getAttribute('TargetMode')||''))invalidSlide();
  const target=rel.getAttribute('Target');
  if(!/^(?:\/ppt\/)?slides\/[a-zA-Z0-9_.-]+\.xml$/.test(target||''))invalidSlide();
  return target.startsWith('/')?target.slice(1):'ppt/'+target;
 });
 if(new Set(paths).size!==paths.length)invalidSlide();
 return {paths,ns,drawing};
}

async function readPptx(file){
 const zip=await officeZip(file);
 const read=async name=>xmlDocument(await zip.read(name)).documentElement;
 const deck=await read('ppt/presentation.xml');
 const {paths,ns,drawing}=slideParts(deck,await read('ppt/_rels/presentation.xml.rels'));
 const lines=[];
 for(const [index,path] of paths.entries()){
  const slide=await read(path);
  if(slide.localName!=='sld'||slide.namespaceURI!==ns)invalidSlide();
  if(['0','false'].includes(slide.getAttribute('show')))continue;
  const contents=children(slide,ns,'cSld');
  if(contents.length!==1)invalidSlide();
  const trees=children(contents[0],ns,'spTree');
  if(trees.length!==1)invalidSlide();
  for(const paragraph of trees[0].getElementsByTagNameNS(drawing,'p')){
   const value=Array.from(paragraph.getElementsByTagNameNS(drawing,'*'),node=>
    node.localName==='t'?node.textContent:node.localName==='br'?' ':'').join('').replace(/\s+/g,' ').trim();
   if(!value)continue;
   // Keep every searchable line short enough to carry its own slide label.
   const characters=Array.from(value);
   for(let start=0;start<characters.length;start+=700){
    lines.push('[Slide '+(index+1)+'] '+characters.slice(start,start+700).join(''));
   }
  }
 }
 return boundedText(lines.join('\n'));
}

const DOCX_TYPE='application/vnd.openxmlformats-officedocument.wordprocessingml.document';
function writeDocx(title,body){
 if(typeof title!=='string'||title.length>120||typeof body!=='string'||!body.trim()||body.length>100000)throw Error('word-export-size');
 const paragraph=(text,heading=false)=>{
  if(!text)return '<w:p/>';
  const rtl=/^[^\p{L}]*\p{Script=Arabic}/u.test(text);
  const runs=text.split('\t').map(part=>part?'<w:t xml:space="preserve">'+xmlEscape(part)+'</w:t>':'').join('<w:tab/>');
  return '<w:p>'+(rtl?'<w:pPr><w:bidi/></w:pPr>':'')+'<w:r>'+
   (heading?'<w:rPr><w:b/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr>':'')+
   runs+'</w:r></w:p>';
 };
 const documentXml='<?xml version="1.0" encoding="UTF-8"?>'+
  '<w:document xmlns:w="'+WORD_NAMESPACES[0]+'"><w:body>'+paragraph(title,true)+
  body.split(/\r\n?|\n/).map(line=>paragraph(line)).join('')+'<w:sectPr/></w:body></w:document>';
 return new Blob([makeZip([
  {name:'[Content_Types].xml',data:'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/word/document.xml" ContentType="'+DOCX_TYPE+'.main+xml"/></Types>'},
  {name:'_rels/.rels',data:'<Relationships xmlns="'+PACKAGE_REL+'"><Relationship Id="rId1" Type="'+PRESENTATION_NAMESPACES[0][2]+'/officeDocument" Target="word/document.xml"/></Relationships>'},
  {name:'word/document.xml',data:documentXml}
 ])],{type:DOCX_TYPE});
}
root.NexusOfficeZip=Object.freeze({readDocx,readPptx,writeDocx,OFFICE_MAX_BYTES});
})(globalThis);
