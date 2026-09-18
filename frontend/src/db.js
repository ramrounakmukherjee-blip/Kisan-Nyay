const DB_NAME='kisan-nyay';
const DB_VERSION=1;
const STORES=['profiles','fields','cases','evidence','syncQueue','settings'];

function openDB(){return new Promise((resolve,reject)=>{const request=indexedDB.open(DB_NAME,DB_VERSION);request.onupgradeneeded=()=>{const db=request.result;for(const store of STORES){if(!db.objectStoreNames.contains(store))db.createObjectStore(store,{keyPath:'id'})}};request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error)})}
export async function put(store,value){const db=await openDB();return new Promise((resolve,reject)=>{const tx=db.transaction(store,'readwrite');tx.objectStore(store).put(value);tx.oncomplete=()=>resolve(value);tx.onerror=()=>reject(tx.error)})}
export async function remove(store,id){const db=await openDB();return new Promise((resolve,reject)=>{const tx=db.transaction(store,'readwrite');tx.objectStore(store).delete(id);tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error)})}
export async function getAll(store){const db=await openDB();return new Promise((resolve,reject)=>{const req=db.transaction(store).objectStore(store).getAll();req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error)})}
export async function getOne(store,id){const db=await openDB();return new Promise((resolve,reject)=>{const req=db.transaction(store).objectStore(store).get(id);req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error)})}
export async function updateCase(id,changes){const current=await getOne('cases',id);if(!current)return null;return put('cases',{...current,...changes,updatedAt:new Date().toISOString()})}
export async function addTimeline(id,event,actor='system'){const current=await getOne('cases',id);if(!current)return null;const timeline=[...(current.timeline||[]),{at:new Date().toISOString(),event,actor}];return updateCase(id,{timeline})}
export async function requestCorrection(caseId,message,kind='photo'){const id=`request-${Date.now()}`;const request={id,caseId,message,kind,status:'open',createdAt:new Date().toISOString()};await put('settings',request);await addTimeline(caseId,`Additional evidence requested: ${message}`,'reviewer');return request}
export async function getOpenRequests(){const all=await getAll('settings');return all.filter(x=>x.id.startsWith('request-')&&x.status==='open')}
export async function completeRequest(id){const item=await getOne('settings',id);if(!item)return null;const completedAt=new Date().toISOString();await put('settings',{...item,status:'pending-sync',completedAt});await put('syncQueue',{id:`sync-${item.caseId}-${item.cloudRequestId||id}`,caseId:item.caseId,operation:'update',state:'waiting',attempts:0,createdAt:completedAt});await updateCase(item.caseId,{status:'pending-sync'});return addTimeline(item.caseId,'Farmer supplied the requested evidence','farmer')}

export async function saveDraft(data){return put('cases',{id:'draft-current',type:'draft',updatedAt:new Date().toISOString(),...data})}
export async function finalizeCase(data){
  const id=`KN-${new Date().getFullYear().toString().slice(-2)}-${crypto.randomUUID().slice(0,8).toUpperCase()}`;
  const createdAt=new Date().toISOString();
  const draftEvidence=(await getAll('evidence')).filter(item=>item.caseId==='draft-current');
  for(const item of draftEvidence)await put('evidence',{...item,caseId:id,syncState:'waiting'});
  const item={...data,id,type:'case',status:'pending-sync',evidenceCount:draftEvidence.length,createdAt,timeline:[{at:createdAt,event:'Evidence saved on device',actor:'farmer'}]};
  await put('cases',item);
  await put('syncQueue',{id:`sync-${id}`,caseId:id,operation:'create',state:'waiting',attempts:0,createdAt});
  await remove('cases','draft-current');
  return item;
}
export async function hashFile(file){const bytes=await file.arrayBuffer();const digest=await crypto.subtle.digest('SHA-256',bytes);return [...new Uint8Array(digest)].map(x=>x.toString(16).padStart(2,'0')).join('')}
export async function saveEvidence(caseId,kind,file){const hash=await hashFile(file);const id=`evidence-${crypto.randomUUID()}`;const capturedAt=new Date().toISOString();const mime=(file.type||'application/octet-stream').split(';')[0];await put('evidence',{id,caseId,kind,blob:file,name:file.name,size:file.size,mime,hash,capturedAt,syncState:'local'});return{id,hash,size:file.size,name:file.name,mime,capturedAt}}
