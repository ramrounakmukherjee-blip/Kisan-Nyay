const region=import.meta.env.VITE_AWS_REGION||'ap-south-1';
const poolId=import.meta.env.VITE_COGNITO_USER_POOL_ID||'';
const clientId=import.meta.env.VITE_COGNITO_CLIENT_ID||'';
export const cognitoEnabled=Boolean(poolId&&clientId);
const endpoint=`https://cognito-idp.${region}.amazonaws.com/`;
const pendingKey='kn-cognito-challenge';

const normalisePhone=value=>`+91${value.replace(/\D/g,'').slice(-10)}`;

async function cognito(action,payload){
  const response=await fetch(endpoint,{method:'POST',headers:{'content-type':'application/x-amz-json-1.1','x-amz-target':`AWSCognitoIdentityProviderService.${action}`},body:JSON.stringify(payload)});
  const data=await response.json().catch(()=>({}));
  if(!response.ok){const error=new Error(data.message||data.Message||'Authentication request failed');error.code=(data.__type||'').split('#').pop();throw error}
  return data;
}

function decodeToken(token){try{const part=token.split('.')[1].replace(/-/g,'+').replace(/_/g,'/');return JSON.parse(atob(part.padEnd(Math.ceil(part.length/4)*4,'=')))}catch{return{}}}
function groupsFromToken(token){const value=decodeToken(token)['cognito:groups'];return Array.isArray(value)?value:[]}
function saveTokens(result){
  if(!result?.IdToken)throw new Error('Cognito did not return a valid session');
  localStorage.setItem('kn-access-token',result.IdToken);
  if(result.RefreshToken)localStorage.setItem('kn-refresh-token',result.RefreshToken);
  localStorage.setItem('kn-token-expiry',String(Date.now()+(result.ExpiresIn||3600)*1000));
}
function acceptSession(result,role){
  saveTokens(result);
  const groups=groupsFromToken(result.IdToken);
  if(role==='officer'&&!groups.includes('Reviewers')){signOut();throw new Error('This account does not have reviewer access')}
  if(role==='farmer'&&groups.includes('Reviewers')){signOut();throw new Error('Use Reviewer access for this account')}
  if(role==='farmer'&&!groups.includes('Farmers')){signOut();throw new Error('Farmer role assignment is not ready. Request a new code and try again.')}
  localStorage.setItem('kn-auth-mode','aws');
  localStorage.setItem('kn-auth-role',role);
  return groups;
}

async function beginSignIn(username,role){
  const result=await cognito('InitiateAuth',{AuthFlow:'USER_AUTH',ClientId:clientId,AuthParameters:{USERNAME:username,PREFERRED_CHALLENGE:'SMS_OTP'}});
  if(result.AuthenticationResult){const groups=acceptSession(result.AuthenticationResult,role);return{authenticated:true,groups}}
  if(result.ChallengeName!=='SMS_OTP')throw new Error('SMS OTP is not available for this account');
  sessionStorage.setItem(pendingKey,JSON.stringify({mode:'signin',username,session:result.Session,role}));
  return{mode:'aws',destination:result.ChallengeParameters?.CODE_DELIVERY_DESTINATION};
}

async function resendUnconfirmed(username,role){
  const resent=await cognito('ResendConfirmationCode',{ClientId:clientId,Username:username});
  sessionStorage.setItem(pendingKey,JSON.stringify({mode:'signup',username,session:null,role}));
  return{mode:'aws',destination:resent.CodeDeliveryDetails?.Destination};
}

export async function beginAuthentication(phone,role='farmer'){
  if(!cognitoEnabled){sessionStorage.setItem(pendingKey,JSON.stringify({mode:'demo',role}));return{mode:'demo'}}
  const username=normalisePhone(phone);
  if(role==='officer'){
    try{return await beginSignIn(username,role)}catch(error){throw new Error('Reviewer account not found or not authorised',{cause:error})}
  }
  try{
    const result=await cognito('SignUp',{ClientId:clientId,Username:username,UserAttributes:[{Name:'phone_number',Value:username}]});
    sessionStorage.setItem(pendingKey,JSON.stringify({mode:'signup',username,session:result.Session||null,role}));
    return{mode:'aws',destination:result.CodeDeliveryDetails?.Destination};
  }catch(error){
    if(error.code!=='UsernameExistsException')throw error;
    try{return await beginSignIn(username,role)}catch(signInError){
      if(signInError.code==='UserNotConfirmedException')return resendUnconfirmed(username,role);
      throw signInError;
    }
  }
}

export async function confirmAuthentication(code,role='farmer'){
  if(!cognitoEnabled){localStorage.setItem('kn-access-token','demo-token');localStorage.setItem('kn-auth-mode','demo');localStorage.setItem('kn-auth-role',role);return{mode:'demo'}}
  const pending=JSON.parse(sessionStorage.getItem(pendingKey)||'null');
  if(!pending)throw new Error('Verification session expired. Request a new code.');
  if(pending.role&&pending.role!==role)throw new Error('Authentication role changed. Request a new code.');
  let result;
  if(pending.mode==='signup'){
    const confirmed=await cognito('ConfirmSignUp',{ClientId:clientId,Username:pending.username,ConfirmationCode:code,...(pending.session?{Session:pending.session}:{})});
    result=await cognito('InitiateAuth',{AuthFlow:'USER_AUTH',ClientId:clientId,AuthParameters:{USERNAME:pending.username},...(confirmed.Session?{Session:confirmed.Session}:{})});
  }else{
    result=await cognito('RespondToAuthChallenge',{ClientId:clientId,ChallengeName:'SMS_OTP',ChallengeResponses:{USERNAME:pending.username,SMS_OTP_CODE:code},Session:pending.session});
  }
  if(!result.AuthenticationResult&&result.ChallengeName==='SMS_OTP'){
    sessionStorage.setItem(pendingKey,JSON.stringify({mode:'signin',username:pending.username,session:result.Session,role}));
    throw new Error('Account confirmed. Cognito sent a new sign-in code; enter it to continue.');
  }
  const groups=acceptSession(result.AuthenticationResult,role);
  sessionStorage.removeItem(pendingKey);
  return{mode:'aws',groups};
}

export async function getIdToken(){
  const token=localStorage.getItem('kn-access-token');
  if(!token||token==='demo-token')return token;
  const expiry=Number(localStorage.getItem('kn-token-expiry')||0);
  if(expiry>Date.now()+60_000)return token;
  const refresh=localStorage.getItem('kn-refresh-token');
  if(!refresh){signOut();return null}
  try{const result=await cognito('InitiateAuth',{AuthFlow:'REFRESH_TOKEN_AUTH',ClientId:clientId,AuthParameters:{REFRESH_TOKEN:refresh}});saveTokens(result.AuthenticationResult);return result.AuthenticationResult.IdToken}catch{signOut();return null}
}

export function signOut(){
  localStorage.removeItem('kn-access-token');
  localStorage.removeItem('kn-refresh-token');
  localStorage.removeItem('kn-token-expiry');
  localStorage.removeItem('kn-auth-mode');
  localStorage.removeItem('kn-auth-role');
  sessionStorage.removeItem(pendingKey);
}
