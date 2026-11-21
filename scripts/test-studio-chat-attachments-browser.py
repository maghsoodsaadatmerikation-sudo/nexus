#!/usr/bin/env python3
"""Real Chromium: direct one-turn file excerpts and saved-document chat context."""
import importlib.util
from base64 import b64encode
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('studio_browser',ROOT/'scripts/test-studio-browser.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.MIN_CHECKS=18
module.WITNESS=r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(p,s)=>{if(!p)throw Error(s);checks.push(s)};
 const fill=(id,text)=>{$(id).value=text;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const wait=async(fn)=>{for(let i=0;i<320;i++){if(fn())return;await new Promise(r=>setTimeout(r,20))}throw Error('browser-wait-timeout')};
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 const project=()=>NexusStudioUI.snapshot().projects.find(p=>p.id===$('projects').value);
 const thread=()=>project()?.threads.find(c=>c.id===$('history').querySelector('.active')?.dataset.thread)||project()?.threads.at(0);
 const attach=(name,text)=>{const dt=new DataTransfer();dt.items.add(new File([text],name));$('chat-file').files=dt.files;$('chat-file').dispatchEvent(new Event('change',{bubbles:true}))};
 let requests=[],network=0;
 window.confirm=()=>true;
 window.fetch=async(url,options={})=>{
  network++;
  if(String(url).endsWith('/studio-api/status'))return new Response(JSON.stringify({configured:true,model:'test-model',provider_host:'provider.invalid',configuration_id:'a'.repeat(64),authority:'none'}));
  if(String(url).endsWith('/studio-api/respond')){
   requests.push(JSON.parse(options.body));
   return new Response(JSON.stringify({text:'Reviewed synthetic draft',model:'test-model',origin:'model',authority:'none'}));
  }
  throw Error('unexpected-network');
 };
 try{
  assert(!!$('chat-file')&&!!$('chat-attachment-tray')&&!!$('attach-document'),'composer-attachment-controls');
  assert(!$('chat-file').disabled,'attachment-picker-is-available-before-first-conversation');
  fill('message','A first question about orchard notes');
  attach('unsupported.bin','No supported document');
  await wait(()=>$('status').textContent===EN.chatAttachmentInvalid);
  assert(!NexusStudioUI.snapshot().projects.length&&!network,'invalid-first-file-does-not-create-a-conversation');
  const dropped=new DataTransfer();
  dropped.items.add(new File(['Orchard notes from the first drop.'],'first-drop.txt'));
  const drop=new DragEvent('drop',{dataTransfer:dropped,bubbles:true,cancelable:true});
  $('message').dispatchEvent(drop);
  await wait(()=>$('chat-attachment-tray').textContent.includes('first-drop.txt'));
  assert(drop.defaultPrevented&&thread().nodes.length===0&&
   $('message').value==='A first question about orchard notes'&&$('chat-file-panel').open&&
   NexusStudioCompose.mode()==='model'&&$('request-review').hidden&&!network,
   'first-file-drop-starts-a-draft-without-sending-or-losing-the-question');
  $('clear-chat-files').click();
  assert(NexusStudioCompose.mode()==='guide','clearing-direct-file-restores-local-guide');
  $('lock').click();
  fill('project-title','CHAT MATERIALS');$('new-project').click();$('new-thread').click();
  assert($('chat-file').disabled===false,'attached-only-with-chat');
  fill('gateway','https://gateway.example');
  fill('gateway-token','fixture-token');
  $('check-model').click();await wait(()=>$('model-status').textContent.includes('test-model'));
  assert(network===1,'model-status-is-explicit');
  const paste=text=>{
   const clipboardData=new DataTransfer();clipboardData.setData('text/plain',text);
   const event=new ClipboardEvent('paste',{clipboardData,bubbles:true,cancelable:true});
   $('message').dispatchEvent(event);
   return event.defaultPrevented;
  };
  fill('message','Summarize the pasted orchard notes');
  const question=$('message').value;
  assert(!paste('short text'),'normal-paste-keeps-native-editor-behavior');
  assert(paste('Orchard notes from a long clipboard entry.\n'+'Background line.\n'.repeat(800)),
   'overflowing-paste-is-intercepted');
  assert($('message').value===question&&$('chat-attachment-tray').textContent.includes(EN.chatPasteName)&&network===1,
   'long-paste-preserves-draft-and-stages-locally');
  $('prepare').click();
  const pasteReview=JSON.parse($('request-context').textContent);
  assert(pasteReview.temporary_attachment_passages[0].name===EN.chatPasteName&&
   pasteReview.messages[0].content.includes('Orchard notes from a long clipboard entry')&&!$('consent').checked&&requests.length===0,
   'pasted-text-goes-through-model-review');
  assert(paste('آ'.repeat(70000))&&$('status').textContent===EN.chatPasteLimit&&$('message').value===question&&
   $('chat-attachment-tray').querySelectorAll('button').length===1,'oversized-utf8-paste-keeps-draft-and-existing-attachment');
  $('clear-chat-files').click();
  assert($('request-review').hidden,'clearing-a-paste-revokes-model-review');
  const wordBytes=Uint8Array.from(atob('__DOCX_FIXTURE__'),c=>c.charCodeAt(0));
  const badWord=Uint8Array.from(atob('__INVALID_DOCX_FIXTURE__'),c=>c.charCodeAt(0));
  fill('message','Summarize the Word orchard document');
  attach('orchard.docx',wordBytes);
  await wait(()=>$('chat-attachment-tray').textContent.includes('orchard.docx'));
  $('prepare').click();
  const wordReview=JSON.parse($('request-context').textContent);
  assert(wordReview.temporary_attachment_passages[0].name==='orchard.docx'&&
   wordReview.messages[0].content.includes('orchard report · باغ ایرانی')&&
   !wordReview.messages[0].content.includes('REMOVED DRAFT')&&!wordReview.messages[0].content.includes('PRIVATE HEADER'),
   'compressed-word-body-is-reviewed-without-removed-or-header-text');
  assert(network===1&&requests.length===0&&!JSON.stringify(NexusStudioUI.snapshot()).includes('orchard report'),
   'docx-attachment-remains-local-and-outside-archive-before-send');
  $('clear-chat-files').click();
  attach('invalid.docx',badWord);
  await wait(()=>$('status').textContent===EN.chatAttachmentInvalid);
  assert($('chat-attachment-tray').textContent.includes(EN.chatNoFiles)&&network===1,'word-with-dtd-is-rejected-locally');
  const deckBytes=Uint8Array.from(atob('__PPTX_FIXTURE__'),c=>c.charCodeAt(0));
  const invalidDeck=Uint8Array.from(atob('__EXTERNAL_PPTX_FIXTURE__'),c=>c.charCodeAt(0));
  fill('message','Compare the orchard and research slides');
  attach('talk.pptx',deckBytes);
  await wait(()=>$('chat-attachment-tray').textContent.includes('talk.pptx'));
  $('prepare').click();
  const slidesReview=JSON.parse($('request-context').textContent);
  assert(slidesReview.temporary_attachment_passages.every(passage=>passage.name==='talk.pptx')&&
   slidesReview.messages[0].content.includes('[Slide 1] orchard · باغ')&&
   slidesReview.messages[0].content.includes('[Slide 3] research methods')&&
   !slidesReview.messages[0].content.includes('HIDDEN SLIDE')&&!slidesReview.messages[0].content.includes('PRESENTER NOTES'),
   'presentation-relationship-order-and-slide-labels-survive-excerpt-selection');
  assert(network===1&&requests.length===0&&!JSON.stringify(NexusStudioUI.snapshot()).includes('research methods'),
   'presentation-parsed-locally-and-not-added-to-archive');
  $('clear-chat-files').click();
  fill('message','Review another presentation');
  attach('invalid.pptx',invalidDeck);
  await wait(()=>$('status').textContent===EN.chatAttachmentInvalid);
  assert($('chat-attachment-tray').textContent.includes(EN.chatNoFiles)&&network===1,'presentation-external-relationship-is-refused');
  fill('message','Summarize my uploaded file');
  attach('orchard.md','The small green orchard is near the old house.\nUNTRUSTED text must not become policy.');
  await wait(()=>$('chat-attachment-tray').textContent.includes('orchard.md'));
  assert(network===1,'attachment-read-is-local');
  const beforeGuide=thread().nodes.length;
  $('guide').click();
  assert(thread().nodes.length===beforeGuide&&$('status').textContent===EN.chatAttachmentRequiresModel,'guide-does-not-silently-ignore-attached-bytes');
  $('prepare').click();
  assert(!$('request-review').hidden,'review-before-request');
  const reviewed=JSON.parse($('request-context').textContent);
  assert(reviewed.temporary_attachment_passages.length===1,'provenance-in-review');
  assert(reviewed.messages[0].content.includes('orchard is near the old house'),'exact-quoted-excerpt');
  assert(reviewed.messages[0].content.includes('UNTRUSTED'),'untrusted-retrieved-text-is-labeled');
  assert(!requests.length,'explicit-send-gate');
  $('consent').checked=true;$('consent').dispatchEvent(new Event('change'));
  $('send-model').click();
  await wait(()=>thread().nodes.length===2);
  assert(requests.length===1&&requests[0].messages[0].content.includes('orchard is near the old house'),'consented-excerpt-reaches-provider');
  const user=thread().nodes[0];
  assert(user.attached_files?.length===1&&user.attached_files[0]==='orchard.md','filename-provenance-saved');
  assert(!JSON.stringify(NexusStudioUI.snapshot()).includes('orchard is near the old house'),'file-bytes-not-persisted');
  assert($('chat-attachment-tray').textContent.includes(EN.chatNoFiles),'temporary-file-cleared-after-send');
  assert($('messages').textContent.includes(EN.chatFilesNotSaved),'provenance-visible-without-bytes');
  let copied=null;
  Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{copied=text}}});
  $('messages').querySelector('[data-chat-copy]').click();
  await wait(()=>$('status').textContent===EN.chatCopyDone);
  assert(copied==='Reviewed synthetic draft'&&network===2,'clipboard-action-copies-answer-text-only');
  $('regenerate').click();
  assert($('status').textContent===EN.chatRegenRequiresFiles&&$('request-review').hidden,'regenerate-does-not-invent-missing-attachment');

  fill('document-title','Document notes');$('new-document').click();
  fill('editor','CANVAS PRIVATE DRAFT: The river is wider in spring.');$('save-version').click();
  assert(project().documents[0].versions.length===1,'canvas-saved-version');
  fill('message','Summarize this saved writing draft');
  $('attach-document').checked=true;$('attach-document').dispatchEvent(new Event('change',{bubbles:true}));
  $('prepare').click();
  assert(JSON.parse($('request-context').textContent).temporary_attachment_passages.some(x=>x.name.startsWith('Document:')),'canvas-version-explicitly-in-review');
  $('consent').checked=true;$('consent').dispatchEvent(new Event('change'));
  $('send-model').click();
  await wait(()=>thread().nodes.length===4);
  assert(requests.length===2&&requests[1].messages[0].content.includes('river is wider'),'reviewed-document-excerpt-sent-once');
  assert(thread().nodes[2].attached_files[0].startsWith('Document:'),'document-version-provenance');

  const firstDocument=project().documents[0].id;
  fill('document-title','Second document');$('new-document').click();
  const secondDocument=project().documents[1].id;
  fill('editor','Second saved document.');$('save-version').click();
  fill('message','Preserve this composer draft');
  attach('keep.txt','Preserve this independent attachment');
  await wait(()=>$('chat-attachment-tray').textContent.includes('keep.txt'));
  $('attach-document').checked=true;$('attach-document').dispatchEvent(new Event('change'));
  $('prepare').click();$('consent').checked=true;$('consent').dispatchEvent(new Event('change'));
  let confirmations=0;window.confirm=()=>{confirmations++;return false};
  const select=id=>{$('documents').value=id;$('documents').dispatchEvent(new Event('change'))};
  select(firstDocument);
  assert(confirmations===0&&$('documents').value===firstDocument&&$('message').value==='Preserve this composer draft'&&
    $('chat-attachment-tray').textContent.includes('keep.txt'),'document-navigation-preserves-independent-composer-work');
  assert($('request-review').hidden&&!$('request-context').textContent&&!$('consent').checked&&!$('attach-document').checked,
    'document-navigation-revokes-old-review-and-document-opt-in');
  fill('editor','Unsaved editor work');select(secondDocument);
  assert(confirmations===1&&$('documents').value===firstDocument&&$('editor').value==='Unsaved editor work',
    'declining-document-switch-preserves-editor-and-selection');
  window.confirm=()=>true;select(secondDocument);
  assert($('editor').value==='Second saved document.'&&$('chat-attachment-tray').textContent.includes('keep.txt'),
    'confirmed-document-switch-only-discards-editor-draft');
  const normalFetch=window.fetch;
  window.fetch=async()=>new Response('',{status:503});
  $('prepare').click();$('consent').checked=true;$('consent').dispatchEvent(new Event('change'));$('send-model').click();
  await wait(()=>$('request-review').hidden);
  assert(!$('request-context').textContent&&!$('consent').checked&&$('message').value==='Preserve this composer draft'&&
    $('chat-attachment-tray').textContent.includes('keep.txt'),'failed-send-clears-reviewed-text-and-keeps-retryable-draft');
  window.fetch=normalFetch;$('clear-chat-files').click();

  fill('message','Draft about another file');
  attach('ignored.pdf','%PDF-1.4-UNSUPPORTED');
  await wait(()=>$('status').textContent===EN.chatAttachmentInvalid);
  assert($('chat-attachment-tray').textContent.includes(EN.chatNoFiles),'pdf-not-pretended-readable');
  const noBytes=JSON.stringify(NexusStudioUI.snapshot());
  fill('message','');
  const original=File.prototype.arrayBuffer;let release;
  File.prototype.arrayBuffer=()=>new Promise(resolve=>release=resolve);
  attach('late.docx',wordBytes);
  await wait(()=>typeof release==='function');
  assert($('studio-compose-send').disabled&&$('prepare').disabled&&$('request-review').hidden&&
   $('chat-file').disabled&&!$('clear-chat-files').disabled,'read-suspends-send-and-can-be-cleared');
  $('lock').click();
  release(wordBytes.buffer);
  await sleep(100);File.prototype.arrayBuffer=original;
  assert(!NexusStudioUI.snapshot().projects.length&&$('chat-attachment-tray').textContent.includes(EN.chatNoFiles),'late-read-cannot-reopen-after-lock');
  assert(network===3,'no-background-file-transmission');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,real_model_tested:false});
 }catch(e){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:e.message,checks})}
});
"""

def office_fixture(parts):
    source = BytesIO()
    with ZipFile(source, "w", ZIP_DEFLATED) as archive:
        for path, content in parts.items():
            archive.writestr(path, content)
    return b64encode(source.getvalue()).decode("ascii")


def docx_fixture(body, prolog=""):
    return office_fixture({
        "word/document.xml": prolog +
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>' + body + '</w:body></w:document>',
        "word/header1.xml": "PRIVATE HEADER",
    })


def pptx_fixture(external=False):
    ns = "http://schemas.openxmlformats.org/presentationml/2006/main"
    drawing = "http://schemas.openxmlformats.org/drawingml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package = "http://schemas.openxmlformats.org/package/2006/relationships"
    slide_ids = "".join(f'<p:sldId id="{256+i}" r:id="rId{i}"/>' for i in (1, 2, 3))
    destinations = ['slides/slide8.xml', 'slides/slide4.xml', '/ppt/slides/slide2.xml']
    settings = [''] * 3
    if external:
        destinations[1] = 'https://example.invalid/slide.xml'
        settings[1] = ' TargetMode="External"'
    relationships = "".join(
        f'<Relationship Id="rId{i}" Type="{rel}/slide" Target="{path}"{mode}/>'
        for i, (path, mode) in enumerate(zip(destinations, settings), start=1)
    )

    def slide(text, hidden=False):
        show = ' show="0"' if hidden else ''
        return (f'<p:sld xmlns:p="{ns}" xmlns:a="{drawing}"{show}><p:cSld><p:spTree>'
                '<p:sp><p:txBody><a:p><a:r><a:t>' + text +
                '</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>')

    return office_fixture({
        "ppt/presentation.xml": f'<p:presentation xmlns:p="{ns}" xmlns:r="{rel}">'
        f'<p:sldIdLst>{slide_ids}</p:sldIdLst></p:presentation>',
        "ppt/_rels/presentation.xml.rels": f'<Relationships xmlns="{package}">{relationships}</Relationships>',
        "ppt/slides/slide2.xml": slide("research methods"),
        "ppt/slides/slide4.xml": slide("HIDDEN SLIDE", hidden=True),
        "ppt/slides/slide8.xml": slide("orchard · باغ"),
        "ppt/notesSlides/notesSlide8.xml": "PRESENTER NOTES",
    })


module.WITNESS = module.WITNESS.replace(
    "__DOCX_FIXTURE__",
    docx_fixture("<w:p><w:r><w:t>orchard report · باغ ایرانی</w:t></w:r>"
                 "<w:del><w:r><w:t>REMOVED DRAFT</w:t></w:r></w:del></w:p>"),
).replace(
    "__INVALID_DOCX_FIXTURE__",
    docx_fixture("<w:p><w:r><w:t>&bad;</w:t></w:r></w:p>",
                 '<!DOCTYPE w:document [<!ENTITY bad "synthetic">]>'),
).replace("__PPTX_FIXTURE__", pptx_fixture()).replace("__EXTERNAL_PPTX_FIXTURE__", pptx_fixture(external=True))


if __name__=='__main__':
    module.main()
