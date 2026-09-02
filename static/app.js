import { createDemoPersona, createDemoSignature, maskDemoRegistration } from "./form-helpers.mjs?v=20260902-id4";

const $ = (selector) => document.querySelector(selector);
const form = $("#generator-form");
let persona = null;
let selectedCase = null;
let selectedType = "";
let currentStep = 1;
let generating = false;
let loadingCase = false;
let caseRequest = 0;
let packageUrl = null;
let packageFilename = "";
let manifest = null;

function setStatus(message, error = false) {
  $("#status").textContent = message;
  $("#status").classList.toggle("error", error);
}
function updateButtons() {
  $("#next-step").disabled = !persona || generating;
  $("#generate").disabled = !persona || !selectedCase || loadingCase || generating;
  $("#randomize").disabled = !selectedType || loadingCase || generating;
  $("#previous-step").disabled = generating;
  $("#case-fields").disabled = generating;
  form.setAttribute("aria-busy", String(generating));
}
function showStep(step) {
  currentStep = step;
  document.querySelectorAll("[data-step]").forEach(panel => { panel.hidden = Number(panel.dataset.step) !== step; });
  document.querySelectorAll("[data-step-indicator]").forEach(item => {
    const number = Number(item.dataset.stepIndicator);
    item.classList.toggle("is-complete", number < step);
    if (number === step) item.setAttribute("aria-current", "step");
    else item.removeAttribute("aria-current");
  });
  setStatus("");
  document.querySelector('[data-step="' + step + '"] .step-title').focus();
}
function renderPairs(root, entries) {
  root.replaceChildren();
  for (const [label, value] of entries) {
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = label;
    dd.textContent = value || "해당 없음";
    root.append(dt, dd);
  }
}
document.querySelectorAll("[data-persona]").forEach(button => {
  button.addEventListener("click", () => {
    if (generating || currentStep !== 1) return;
    persona = createDemoPersona(button.dataset.persona);
    document.querySelectorAll("[data-persona]").forEach(other => other.setAttribute("aria-pressed", String(other === button)));
    $("#persona-feedback").textContent = persona.name + " · " + persona.birth_date + " · " + persona.nationality + " · " + maskDemoRegistration(persona.registration_number);
    $("#applicant-summary").textContent = $("#persona-feedback").textContent;
    updateButtons();
  });
});
function renderCase(item) {
  selectedCase = item;
  $("#case-preview").hidden = false;
  $("#case-preview").replaceChildren();
  const header = document.createElement("h3");
  header.textContent = item.type_label + " · " + item.id;
  const dl = document.createElement("dl");
  renderPairs(dl, [
    ["사고 일시", item.accident_date + " " + item.accident_time],
    ["사업장", item.workplace + " · " + item.occupation],
    ["사업장 관리번호", item.demo_workplace.management_number],
    ["사업주명", item.demo_workplace.representative_name],
    ["사업장 연락처", item.demo_workplace.phone],
    ["목격자", item.witness],
    ["목격자 연락처", item.demo_accident.witness_phone],
    ["사고 경위", item.accident_description],
    ["입력용 증빙", item.input_documents.join("\n")],
  ]);
  $("#case-preview").append(header, dl);
}
async function loadRandomCase() {
  if (!selectedType || generating) return;
  const requestId = ++caseRequest;
  selectedCase = null;
  loadingCase = true;
  $("#case-preview").hidden = true;
  updateButtons();
  setStatus("합성 케이스를 고르고 있습니다…");
  try {
    const response = await fetch("/api/cases/random?case_type=" + encodeURIComponent(selectedType));
    if (!response.ok) throw new Error("케이스를 불러오지 못했습니다. 다시 시도해주세요.");
    const item = await response.json();
    if (requestId !== caseRequest) return;
    renderCase(item);
    setStatus("케이스가 준비되었습니다.");
  } catch (error) {
    if (requestId === caseRequest) setStatus(error.message, true);
  } finally {
    if (requestId === caseRequest) { loadingCase = false; updateButtons(); }
  }
}
async function initialize() {
  try {
    const [response, configResponse] = await Promise.all([fetch("/api/case-types"), fetch("/api/config", {cache: "no-store"})]);
    if (!response.ok || !configResponse.ok) throw new Error("사고 유형 또는 서비스 연결 설정을 불러오지 못했습니다.");
    const target = await configResponse.json();
    $("#service-target").textContent = "계정 생성·신청 대상: " + (target.environment === "production" ? "운영 서비스" : target.environment === "local" ? "로컬 서비스" : "별도 서비스") + " · " + target.app_url + " (제너레이터는 로컬 실행)";
    const types = await response.json();
    $("#case-total").textContent = types.reduce((sum, item) => sum + item.case_count, 0);
    $("#case-types").replaceChildren();
    for (const item of types) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "case-button";
      button.setAttribute("aria-pressed", "false");
      const title = document.createElement("strong");
      const detail = document.createElement("small");
      title.textContent = item.label;
      detail.textContent = item.summary + " · " + item.case_count + "개";
      button.append(title, detail);
      button.addEventListener("click", () => {
        if (generating) return;
        selectedType = item.code;
        $("#case-types").querySelectorAll("button").forEach(other => {
          other.classList.toggle("active", other === button);
          other.setAttribute("aria-pressed", String(other === button));
        });
        void loadRandomCase();
      });
      $("#case-types").append(button);
    }
  } catch (error) {
    $("#case-types").textContent = error.message;
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "secondary";
    retry.textContent = "다시 불러오기";
    retry.onclick = () => { retry.disabled = true; void initialize(); };
    $("#case-types").append(retry);
  }
}
function download(url, filename) {
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
}
function releasePackage() {
  if (packageUrl) URL.revokeObjectURL(packageUrl);
  packageUrl = null;
  packageFilename = "";
}
function renderCompletion() {
  const person = manifest.applicant;
  const workplace = manifest.workplace;
  const accident = manifest.accident;
  const account = manifest.demo_account;
  renderPairs($("#completed-persona"), [
    ["재해 근로자", person.name], ["생년월일", person.birth_date], ["국적", person.nationality],
    ["등록번호 (시연용·화면 마스킹)", maskDemoRegistration(person.registration_number)], ["성별 (시연 설정)", person.sex === "male" ? "남성" : person.sex === "female" ? "여성" : "미지정"], ["연락처", person.phone],
    ["주소", person.address], ["화면 언어", person.preferred_language], ["로그인 이메일", account.email],
    ["시연 비밀번호", account.password], ["사고 유형", manifest.case.type_label],
    ["신청 서비스", manifest.service_target.app_url],
    ["사고 일시", accident.accident_date + " " + accident.accident_time],
  ]);
  renderPairs($("#completed-workplace"), [
    ["사업장", workplace.company_name], ["사업장 관리번호", workplace.management_number],
    ["사업자등록번호", workplace.business_registration_no], ["사업주명", workplace.representative_name],
    ["사업장 연락처", workplace.phone], ["사업장 주소", workplace.address], ["담당 업무", workplace.occupation],
    ["목격자", accident.witness_name], ["목격자 연락처", accident.witness_phone],
    ["목격자 관계", accident.witness_relationship], ["사고 경위", accident.raw_description],
  ]);
  $("#completed-signature").src = manifest.signature.image;
  $("#signature-description").textContent = "서명자: " + manifest.signature.name + (manifest.case.case_type === "survivor" ? " (유족 청구인)" : "");
  const ready = account.status === "created" && !account.email_confirmation_required;
  $("#account-result").textContent = account.message;
  $("#account-result").classList.toggle("warning", !ready);
  $("#start-application").disabled = !ready;
  $("#download-signature").disabled = !manifest.signature.image;
  $("#completed-files").textContent = "ZIP: 증빙 PDF 3종 + 00_시연_입력_가이드.json + " + manifest.signature.file;
  $("#guide-steps").replaceChildren();
  for (const step of manifest.steps) {
    const section = document.createElement("section");
    const heading = document.createElement("h4");
    heading.textContent = (step.display_step ? "STEP " + step.display_step + " · " : "") + step.title;
    section.append(heading);
    if (step.fields || step.expected || step.reference_facts) {
      const pre = document.createElement("pre");
      pre.textContent = JSON.stringify(step.fields || step.expected || step.reference_facts, null, 2);
      section.append(pre);
    }
    for (const instruction of [...(step.files || []), ...(step.instructions || [])]) {
      const p = document.createElement("p");
      p.textContent = instruction;
      section.append(p);
    }
    $("#guide-steps").append(section);
  }
}
$("#next-step").onclick = () => { if (persona && !generating) showStep(2); };
$("#previous-step").onclick = () => { if (!generating) showStep(1); };
$("#randomize").onclick = loadRandomCase;
$("#download-again").onclick = () => { if (packageUrl) download(packageUrl, packageFilename); };
$("#download-guide").onclick = () => {
  if (!manifest) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(manifest, null, 2)], {type:"application/json"}));
  download(url, "00_시연_입력_가이드.json");
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
$("#download-signature").onclick = () => { if (manifest?.signature.image) download(manifest.signature.image, manifest.signature.file); };
$("#start-application").onclick = () => {
  if ($("#start-application").disabled) return;
  // Same-tab navigation also works when the host browser blocks pop-ups.
  window.location.assign(manifest.service_target.application_url);
};
$("#start-over").onclick = () => {
  caseRequest++;
  releasePackage();
  persona = null;
  selectedCase = null;
  selectedType = "";
  manifest = null;
  loadingCase = false;
  $("#completed-signature").removeAttribute("src");
  $("#completed-persona").replaceChildren();
  $("#completed-workplace").replaceChildren();
  $("#guide-steps").replaceChildren();
  $("#persona-feedback").textContent = "내국인 또는 외국인 예시를 선택해주세요.";
  document.querySelectorAll('[aria-pressed]').forEach(button => { button.classList.remove("active"); button.setAttribute("aria-pressed", "false"); });
  $("#case-preview").hidden = true;
  updateButtons();
  showStep(1);
};
form.addEventListener("submit", async event => {
  event.preventDefault();
  if (currentStep !== 2 || !persona || !selectedCase || loadingCase || generating) return;
  generating = true;
  updateButtons();
  setStatus("데모 계정과 시연 자료를 생성하고 있습니다…");
  try {
    const signature = createDemoSignature(selectedCase.case_type === "survivor" ? "김유족" : persona.name);
    const response = await fetch("/api/generate?response_format=json", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({...persona, case_type:selectedType, case_id:selectedCase.id, signature_image:signature}),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(Array.isArray(result.detail) ? result.detail.map(item => item.msg).join(" ") : result.detail || "패키지 생성에 실패했습니다.");
    const bytes = Uint8Array.from(atob(result.package_base64), character => character.charCodeAt(0));
    releasePackage();
    packageUrl = URL.createObjectURL(new Blob([bytes], {type:"application/zip"}));
    packageFilename = result.filename;
    manifest = result.manifest;
    renderCompletion();
    showStep(3);
    download(packageUrl, packageFilename);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    generating = false;
    updateButtons();
  }
});
updateButtons();
void initialize();
