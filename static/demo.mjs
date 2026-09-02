import {createDemoPersona,createDemoRegistration,createDemoSignature,maskDemoRegistration,parseBirthDate} from './form-helpers.mjs';
// Deliberately fixed: neither query strings nor browser storage can override it.
export const API = 'https://sanjae-oneshot.co.kr/api/v1/demo';
const $ = selector => document.querySelector(selector);
const form = $('#demo-form');
let persona, selectedCase, selectedType, busy = false, requestNumber = 0;
let registrationIdentity = '';
function status(message, failed = false) { $('#status').textContent=message; $('#status').classList.toggle('error',failed); }
function step(number) {
  document.querySelectorAll('[data-step]').forEach(node=>node.hidden=Number(node.dataset.step)!==number);
  document.querySelectorAll('[data-indicator]').forEach(node=>{if(Number(node.dataset.indicator)===number) node.setAttribute('aria-current','step'); else node.removeAttribute('aria-current');});
  document.querySelector(`[data-step="${number}"] .step-title`).focus();
  window.scrollTo({top:0,behavior:'smooth'}); status('');
}
function buttons(){
  $('#next').disabled=busy||!persona||!$('#synthetic-only').checked;
  $('#generate').disabled=busy||!persona||!selectedCase;
  $('#randomize').disabled=busy||!selectedType;
  $('#back').disabled=busy;form.setAttribute('aria-busy',String(busy));
}
function readPerson(){
  const values=Object.fromEntries(new FormData(form));
  const birth=parseBirthDate(values.year,values.month,values.day);
  const kind=['대한민국','한국','kr','kor','south korea','republic of korea'].includes(values.nationality?.trim().toLowerCase())?'domestic':'foreign';
  const identity=[birth.iso,values.sex,kind].join('|');
  const registration=identity===registrationIdentity&&persona?persona.registration_number:createDemoRegistration(birth.iso,Math.random,kind,values.sex||null);
  if(!birth.iso||!registration||!values.sex||!values.name?.trim()||values.name.trim().length<2||!values.nationality?.trim()||values.phone?.trim().length<8||values.address?.trim().length<5){persona=null;buttons();return;}
  persona={name:values.name.trim(),birth_date:birth.iso,nationality:values.nationality.trim(),sex:values.sex,address:values.address.trim(),phone:values.phone.trim(),preferred_language:values.preferred_language,registration_number:registration};
  registrationIdentity=identity;$('#registration-preview').textContent='시연 등록번호: '+maskDemoRegistration(registration);buttons();
}
form.addEventListener('input',readPerson);
document.querySelectorAll('[data-persona]').forEach(button=>button.onclick=()=>{
  const sample=createDemoPersona(button.dataset.persona);
  for(const key of ['name','nationality','sex','address','phone','preferred_language']) form.elements.namedItem(key).value=sample[key];
  [form.elements.namedItem('year').value,form.elements.namedItem('month').value,form.elements.namedItem('day').value]=sample.birth_date.split('-');
  registrationIdentity=''; readPerson();
});
function pairs(root,entries){root.replaceChildren();for(const [label,value] of entries){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=String(value||'해당 없음');root.append(dt,dd);}}
async function request(path,options){
  const response=await fetch(API+path,{cache:'no-store',credentials:'omit',...options});const result=await response.json();
  if(!response.ok) throw new Error(typeof result.detail==='string'?result.detail:'입력 정보나 서비스 연결 상태를 확인해주세요.');return result;
}
async function randomCase(){
  const version=++requestNumber; selectedCase=null;buttons();status('사고 정보를 준비하고 있습니다…');
  try{const item=await request('/cases/random?case_type='+encodeURIComponent(selectedType));if(version!==requestNumber)return;selectedCase=item;
    pairs($('#case-preview'),[['사고 유형',item.type_label],['사업장',item.workplace],['사업장 관리번호',item.demo_workplace.management_number],['사업주명',item.demo_workplace.representative_name],['사업장 연락처',item.demo_workplace.phone],['사고 일시',item.accident_date+' '+item.accident_time],['목격자',item.witness],['목격자 연락처',item.demo_accident.witness_phone],['사고 경위',item.accident_description],['준비 서류',item.input_documents.join(', ')]]);status('');
  }catch(error){status(error.message,true);}finally{buttons();}
}
async function initialize(){
  try{const types=await request('/case-types');$('#case-types').replaceChildren();for(const item of types){const button=document.createElement('button');button.type='button';button.className='case-button';button.textContent=item.label;button.onclick=()=>{if(busy)return;selectedType=item.code;document.querySelectorAll('.case-button').forEach(node=>{node.classList.toggle('active',node===button);node.setAttribute('aria-pressed',String(node===button));});void randomCase();};$('#case-types').append(button);}}
  catch(error){status(error.message,true);const retry=document.createElement('button');retry.type='button';retry.textContent='다시 연결';retry.onclick=()=>{retry.remove();void initialize();};$('#case-types').append(retry);}
}
$('#next').onclick=()=>{readPerson();if(persona&&$('#synthetic-only').checked)step(2);};
$('#back').onclick=()=>step(1);$('#randomize').onclick=randomCase;$('#restart').onclick=()=>window.location.reload();
form.onsubmit=async event=>{
  event.preventDefault();if(busy||!persona||!selectedCase||!$('#synthetic-only').checked)return;
  busy=true;buttons();status('준비 서류를 생성하고 운영 DB에 암호화해 보관 중입니다…');
  try{
    const result=await request('/prepare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...persona,synthetic_only:true,signature_image:createDemoSignature(selectedType==='survivor'?'김유족':persona.name),case_type:selectedType,case_id:selectedCase.id})});
    const guide=result.guide;const basic=guide.steps.find(item=>item.id==='basic').fields;
    pairs($('#person-result'),[['성명',persona.name],['생년월일',persona.birth_date],['국적',persona.nationality],['연락처',persona.phone],['주소',persona.address],['등록번호',maskDemoRegistration(persona.registration_number)],['화면 언어',persona.preferred_language],['신청인',basic.applicant.name]]);
    pairs($('#case-result'),Object.entries(basic.workplace).map(([key,value])=>[({company_name:'사업장',management_number:'사업장 관리번호',business_registration_no:'사업자등록번호',representative_name:'사업주명',phone:'사업장 연락처',address:'사업장 주소',occupation:'담당 업무',job_position:'직책'})[key]||key,value]));
    $('#signature').src=guide.signature.image;$('#files-result').textContent='임시 보관 완료: '+[...result.files,'시연_입력_가이드.json','서명 PNG'].join(' · ');
    const target=new URL(result.handoff_url);if(target.origin!=='https://sanjae-oneshot.co.kr')throw new Error('체험 주소를 확인할 수 없습니다.');$('#experience').href=target.href;step(3);
  }catch(error){status(error.message,true);}finally{busy=false;buttons();}
};
void initialize();
