// These are synthetic demo identifiers, not real identity or credential generation.
export function parseBirthDate(yearText, monthText, dayText, today = new Date()) {
  if (!/^[0-9]{4}$/.test(yearText) || Number(yearText) < 1800 || Number(yearText) > today.getFullYear()) {
    return { iso: "", field: "year", error: `년은 1800~${today.getFullYear()} 사이의 네 자리 숫자로 입력해주세요.` };
  }
  if (!/^[0-9]{1,2}$/.test(monthText) || Number(monthText) < 1 || Number(monthText) > 12) {
    return { iso: "", field: "month", error: "월은 1~12 사이의 숫자로 입력해주세요." };
  }
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
  if (!/^[0-9]{1,2}$/.test(dayText) || day < 1 || day > lastDay) {
    return { iso: "", field: "day", error: `선택한 년·월의 일은 1~${lastDay} 사이여야 합니다.` };
  }
  const iso = `${yearText}-${monthText.padStart(2, "0")}-${dayText.padStart(2, "0")}`;
  const currentDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  if (iso > currentDate) return { iso: "", field: "day", error: "생년월일은 오늘 이후의 날짜일 수 없습니다." };
  return { iso, field: null, error: "" };
}

export function createDemoRegistration(iso, random = Math.random, personaKind = null, sex = null) {
  const match = /^([0-9]{4})-([0-9]{2})-([0-9]{2})$/.exec(iso);
  if (!match || !parseBirthDate(match[1], match[2], match[3]).iso) return "";
  // Only constrain nationality for an explicitly selected demo persona.
  // Manual input never infers nationality or gender from a name or language.
  const century = Math.floor(Number(match[1]) / 100);
  const groups = {
    domestic: { 18: [9, 0], 19: [1, 2], 20: [3, 4] },
    foreign: { 19: [5, 6], 20: [7, 8] },
  };
  let codes = (groups[personaKind] || { 18: [9, 0], 19: [1, 2, 5, 6], 20: [3, 4, 7, 8] })[century];
  if (!codes) return "";
  if (sex !== null) {
    if (!["male", "female"].includes(sex)) throw new RangeError("지원하지 않는 시연 성별입니다.");
    codes = codes.filter(code => (code % 2 === 1) === (sex === "male"));
  }
  const digit = codes[Math.floor(random() * codes.length)];
  const suffix = String(Math.floor(random() * 1_000_000)).padStart(6, "0");
  return `${iso.replaceAll("-", "").slice(2)}-${digit}${suffix}`;
}

export function maskDemoRegistration(number) {
  return number.replace(/^(\d{6}-\d)\d{6}$/, "$1******");
}

// Sex is an explicit attribute of these fictional samples, never inferred from
// a real person's name. It fixes the first trailing digit for each persona.
const DEMO_PERSONAS = {
  domestic: [
    { name: "김민준", birth_date: "1991-04-18", sex: "male", preferred_language: "ko", address: "서울특별시 구로구 시연로 25, 테스트주택 101호 (가상)" },
    { name: "이서연", birth_date: "1988-11-07", sex: "female", preferred_language: "ko", address: "경기도 수원시 시연로 42, 테스트주택 202호 (가상)" },
    { name: "박지훈", birth_date: "2001-06-23", sex: "male", preferred_language: "ko", address: "인천광역시 서구 시연로 77, 테스트주택 303호 (가상)" },
  ],
  foreign: [
    { name: "NGUYEN VAN LONG", birth_date: "1994-03-12", sex: "male", preferred_language: "vi", address: "경기도 안산시 단원구 시연로 100, 테스트기숙사 201호 (가상)" },
    { name: "MARIA SANTOS", birth_date: "1990-09-05", sex: "female", preferred_language: "fil", address: "경기도 이천시 시연로 18, 테스트기숙사 202호 (가상)" },
    { name: "ALEX MORGAN", birth_date: "2000-02-29", sex: "male", preferred_language: "en", address: "충청남도 천안시 시연로 42, 테스트기숙사 203호 (가상)" },
  ],
};

export function createDemoPersona(kind, random = Math.random, uniqueId = crypto.randomUUID()) {
  const options = DEMO_PERSONAS[kind];
  if (!options) throw new RangeError("지원하지 않는 예시 페르소나입니다.");
  const persona = options[Math.floor(random() * options.length)];
  const suffix = String(uniqueId).toLowerCase().replace(/[^a-z0-9]/g, "").slice(0, 32);
  if (!suffix) throw new RangeError("시연용 식별자가 필요합니다.");
  return {
    ...persona,
    nationality: kind === "domestic" ? "대한민국" : { vi: "베트남", fil: "필리핀", en: "캐나다" }[persona.preferred_language],
    phone: `010-0000-${String(Math.floor(random() * 10000)).padStart(4, "0")}`,
    email: `demo.${kind === "domestic" ? "ko" : "intl"}.${suffix}@example.com`,
    registration_number: createDemoRegistration(persona.birth_date, random, kind, persona.sex),
  };
}

export function createDemoSignature(name, makeCanvas = () => document.createElement("canvas")) {
  if (!name.trim()) throw new RangeError("서명을 만들 이름이 필요합니다.");
  const canvas = makeCanvas();
  canvas.width = 960;
  canvas.height = 280;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("이 브라우저에서 서명 이미지를 만들 수 없습니다.");
  let size = 130;
  const font = () => `italic ${size}px "Malgun Gothic", "Apple SD Gothic Neo", cursive`;
  context.font = font();
  while (context.measureText(name).width > 830 && size > 20) { size -= 2; context.font = font(); }
  context.fillStyle = "#17243a";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.save();
  context.translate(480, 130);
  context.rotate(-0.035);
  context.fillText(name, 0, 0, 830);
  context.restore();
  context.strokeStyle = "#17243a";
  context.lineWidth = 3;
  context.beginPath();
  context.moveTo(210, 214);
  context.bezierCurveTo(395, 229, 594, 205, 750, 203);
  context.stroke();
  return canvas.toDataURL("image/png");
}
