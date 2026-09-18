import {cloudEnabled,completeCloudCorrection,completeEvidence,createCloudCase,getCloudCase,getUploadUrl,listCloudCases,submitCloudCase,uploadEvidence} from './aws.js';
import {getAll,put} from './db.js';

let running=false;
const canSync=()=>cloudEnabled&&navigator.onLine&&localStorage.getItem('kn-auth-mode')==='aws'&&localStorage.getItem('kn-auth-role')==='farmer';

async function pullCorrectionRequests(){
  const cloudCases=(await listCloudCases()).items||[];
  const [localCases,settings]=await Promise.all([getAll('cases'),getAll('settings')]);
  for(const cloudCase of cloudCases){
    const local=localCases.find(item=>item.cloudCaseId===cloudCase.caseId);
    if(!local)continue;
    const detail=await getCloudCase(cloudCase.caseId);
    for(const request of detail.records.filter(item=>item.SK?.startsWith('REQUEST#')&&item.status==='OPEN')){
      const id=`cloud-${request.requestId}`;
      const existing=settings.find(item=>item.id===id);
      if(existing&&existing.status!=='open')continue;
      await put('settings',{id,caseId:local.id,cloudCaseId:cloudCase.caseId,cloudRequestId:request.requestId,message:request.message,kind:request.evidenceKind||'photo',status:'open',createdAt:request.createdAt,source:'aws'});
    }
  }
}

export async function syncPending(onProgress=()=>{}){
  if(running||!canSync())return{skipped:true,reason:running?'already-running':'cloud-unavailable'};
  running=true;
  const result={completed:0,failed:0};
  try{
    const jobs=(await getAll('syncQueue')).filter(item=>['waiting','failed','syncing'].includes(item.state));
    const allCases=await getAll('cases');
    for(const originalJob of jobs){
      let job=originalJob;
      try{
        job={...job,state:'syncing',lastError:null,lastAttemptAt:new Date().toISOString()};
        await put('syncQueue',job);
        const local=allCases.find(item=>item.id===job.caseId&&item.type==='case');
        if(!local)throw new Error('Local case not found');
        await put('cases',{...local,status:'syncing',updatedAt:new Date().toISOString()});
        onProgress({caseId:job.caseId,state:'creating'});
        const cloud=local.cloudCaseId?{caseId:local.cloudCaseId}:await createCloudCase({crop:local.crop,incidentType:local.incident,fieldId:local.field,damageRange:local.damage,occurredAt:local.createdAt},job.id);
        const evidence=(await getAll('evidence')).filter(item=>item.caseId===job.caseId);
        let uploaded=evidence.filter(item=>item.syncState==='uploaded'&&item.cloudCaseId===cloud.caseId).length;
        for(const item of evidence){
          if(item.syncState==='uploaded'&&item.cloudCaseId===cloud.caseId)continue;
          onProgress({caseId:job.caseId,state:'uploading',uploaded,total:evidence.length});
          const signed=await getUploadUrl(cloud.caseId,{clientEvidenceId:item.id,kind:item.kind,contentType:item.mime,sha256:item.hash,size:item.size,capturedAt:item.capturedAt});
          if(signed.uploadRequired!==false)await uploadEvidence(signed.uploadUrl,item.blob,signed.requiredHeaders);
          await completeEvidence(cloud.caseId,signed.evidenceId);
          await put('evidence',{...item,syncState:'uploaded',cloudCaseId:cloud.caseId,cloudEvidenceId:signed.evidenceId,syncedAt:new Date().toISOString()});
          uploaded++;
        }
        const correctionRequests=(await getAll('settings')).filter(item=>item.caseId===job.caseId&&item.status==='pending-sync'&&item.cloudRequestId);
        for(const request of correctionRequests){
          await completeCloudCorrection(cloud.caseId,request.cloudRequestId);
          await put('settings',{...request,status:'completed',syncedAt:new Date().toISOString()});
        }
        onProgress({caseId:job.caseId,state:'submitting',uploaded,total:evidence.length});
        const submitted=await submitCloudCase(cloud.caseId);
        const completedAt=new Date().toISOString();
        await put('syncQueue',{...job,state:'completed',cloudCaseId:cloud.caseId,completedAt});
        await put('cases',{...local,status:'synchronized',cloudStatus:submitted.status,cloudCaseId:cloud.caseId,syncedAt:completedAt,updatedAt:completedAt,timeline:[...(local.timeline||[]),{at:completedAt,event:'Evidence synchronized to secure cloud storage',actor:'system'}]});
        onProgress({caseId:job.caseId,state:'completed',uploaded,total:evidence.length});
        result.completed++;
      }catch(error){
        const failedAt=new Date().toISOString();
        await put('syncQueue',{...job,state:'failed',attempts:(job.attempts||0)+1,lastError:error.message,lastAttemptAt:failedAt});
        const local=allCases.find(item=>item.id===job.caseId);
        if(local)await put('cases',{...local,status:'sync-failed',syncError:error.message,updatedAt:failedAt});
        onProgress({caseId:job.caseId,state:'failed',error:error.message});
        result.failed++;
      }
    }
    await pullCorrectionRequests();
    return result;
  }finally{running=false}
}
