import {getIdToken} from './auth.js';

const config={apiUrl:(import.meta.env.VITE_AWS_API_URL||'').replace(/\/$/,''),region:import.meta.env.VITE_AWS_REGION||'ap-south-1'};
export const cloudEnabled=Boolean(config.apiUrl);

async function request(path,options={}){
  if(!cloudEnabled)throw new Error('AWS cloud sync is not configured');
  const token=await getIdToken();
  if(!token||token==='demo-token')throw new Error('Sign in with AWS before cloud synchronization');
  const response=await fetch(`${config.apiUrl}${path}`,{...options,headers:{...(options.body?{'content-type':'application/json'}:{}),authorization:`Bearer ${token}`,...options.headers}});
  if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(body.message||`Request failed (${response.status})`)}
  return response.status===204?null:response.json();
}
export async function createCloudCase(data,operationId){return request('/cases',{method:'POST',headers:{'idempotency-key':operationId},body:JSON.stringify(data)})}
export async function getUploadUrl(caseId,evidence){return request(`/cases/${encodeURIComponent(caseId)}/evidence-url`,{method:'POST',body:JSON.stringify(evidence)})}
export async function uploadEvidence(url,file,requiredHeaders){const result=await fetch(url,{method:'PUT',headers:requiredHeaders,body:file});if(!result.ok)throw new Error(`Evidence upload failed (${result.status})`)}
export async function completeEvidence(caseId,evidenceId){return request(`/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(evidenceId)}/complete`,{method:'POST',body:'{}'})}
export async function submitCloudCase(caseId){return request(`/cases/${encodeURIComponent(caseId)}/submit`,{method:'POST',body:'{}'})}
export async function listCloudCases(){return request('/cases')}
export async function getCloudCase(caseId){return request(`/cases/${encodeURIComponent(caseId)}`)}
export async function requestCloudCorrection(caseId,data){return request(`/cases/${encodeURIComponent(caseId)}/requests`,{method:'POST',body:JSON.stringify(data)})}
export async function completeCloudCorrection(caseId,requestId){return request(`/cases/${encodeURIComponent(caseId)}/requests/${encodeURIComponent(requestId)}/complete`,{method:'POST',body:'{}'})}
export async function getHealth(){if(!cloudEnabled)throw new Error('AWS cloud sync is not configured');const response=await fetch(`${config.apiUrl}/health`);if(!response.ok)throw new Error('Cloud service is unavailable');return response.json()}
