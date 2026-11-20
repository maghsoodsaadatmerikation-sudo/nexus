/* Bounded ZIP and XML readers reused by Studio and the offline file desk. */
(function(root){'use strict';
const PREVIEW_LIMIT=512*1024;
/* OFFICE_ZIP_READER */
const DOCX_MAX_BYTES=2*1024*1024;
const WORD_NAMESPACES=[
 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
 'http://purl.oclc.org/ooxml/wordprocessingml/main'
];

async function readDocx(file){
 if(!Number.isSafeInteger(file.size)||file.size<1||file.size>DOCX_MAX_BYTES)throw Error('docx-size');
 const bytes=new Uint8Array(await file.arrayBuffer());
 if(bytes.length!==file.size)throw Error('docx-size');
 const zip=zipReader(bytes);
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

root.NexusOfficeZip=Object.freeze({readDocx,DOCX_MAX_BYTES});
})(globalThis);
