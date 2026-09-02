import test from "node:test";
import assert from "node:assert/strict";
import { createDemoRegistration, createDemoPersona, parseBirthDate, maskDemoRegistration } from "../static/form-helpers.mjs";

const today = new Date(2026, 8, 2);

for (const [parts, expected] of [
  [["1991", "04", "18"], "1991-04-18"],
  [["1994", "3", "2"], "1994-03-02"],
  [["2000", "2", "29"], "2000-02-29"],
  [["2024", "02", "29"], "2024-02-29"],
  [["2026", "9", "2"], "2026-09-02"],
]) {
  test(`split date normalizes ${parts.join("-")}`, () => {
    assert.deepEqual(parseBirthDate(...parts, today), { iso: expected, field: null, error: "" });
  });
}

for (const [parts, field] of [
  [["", "", ""], "year"],
  [["199", "4", "18"], "year"],
  [["1799", "4", "18"], "year"],
  [["2027", "1", "1"], "year"],
  [["199a", "4", "18"], "year"],
  [["1991", "", "18"], "month"],
  [["1991", "0", "18"], "month"],
  [["1991", "13", "18"], "month"],
  [["1991", "4", ""], "day"],
  [["1991", "4", "0"], "day"],
  [["1991", "4", "31"], "day"],
  [["1900", "2", "29"], "day"],
  [["2025", "2", "29"], "day"],
  [["2026", "9", "3"], "day"],
  [["1991", "04", "a"], "day"],
]) {
  test(`invalid date rejected: ${JSON.stringify(parts)}`, () => {
    const result = parseBirthDate(...parts, today);
    assert.equal(result.iso, "");
    assert.equal(result.field, field);
    assert.ok(result.error);
  });
}

for (const [birth, digits] of [["1891-04-18", [9, 0]], ["1994-03-12", [1, 2, 5, 6]], ["2004-03-12", [3, 4, 7, 8]]]) {
  test(`synthetic first digit matches birth century: ${birth}`, () => {
    for (let index = 0; index < digits.length; index++) {
      const number = createDemoRegistration(birth, () => (index + 0.5) / digits.length);
      assert.equal(number.slice(0, 8), `${birth.replaceAll("-", "").slice(2)}-${digits[index]}`);
      assert.match(number, /^\d{6}-\d{7}$/);
      assert.equal(maskDemoRegistration(number), `${number.slice(0, 8)}******`);
    }
  });
}

test("no identifier is generated from missing or invalid birth dates", () => {
  for (const date of ["", "1994-03", "2025-02-29", "1994-13-12", "abcd-03-12", "1994-3-2"]) {
    assert.equal(createDemoRegistration(date), "");
  }
});

for (const kind of ["domestic", "foreign"]) {
  for (const random of [0, 0.49, 0.999]) {
    test(`${kind} persona ${random} fills valid synthetic data`, () => {
      const persona = createDemoPersona(kind, () => random, "test-demo-123");
      assert.ok(parseBirthDate(...persona.birth_date.split("-"), today).iso);
      const digit = persona.registration_number[7];
      const bornAfter2000 = Number(persona.birth_date.slice(0, 4)) >= 2000;
      const allowed = kind === "domestic" ? (bornAfter2000 ? "34" : "12") : (bornAfter2000 ? "78" : "56");
      assert.ok(allowed.includes(digit));
      assert.match(persona.registration_number, /^\d{6}-\d{7}$/);
      assert.equal(Number(digit) % 2, persona.sex === "male" ? 1 : 0);
      assert.equal(persona.registration_number.slice(0, 6), persona.birth_date.replaceAll("-", "").slice(2));
      assert.match(persona.email, /^demo\.(ko|intl)\.testdemo123@example\.com$/);
      assert.match(persona.phone, /^010-0000-\d{4}$/);
      assert.ok(persona.address.includes("가상"));
      if (kind === "domestic") assert.equal(persona.preferred_language, "ko");
      else {
        assert.match(persona.name, /^[A-Z ]+$/);
        assert.ok(["en", "vi", "fil"].includes(persona.preferred_language));
      }
    });
  }
}

test("each persona click uses a fresh email without mutating the sample", () => {
  const first = createDemoPersona("foreign", () => 0, "first");
  const second = createDemoPersona("foreign", () => 0, "second");
  assert.notEqual(first.email, second.email);
  first.name = "edited";
  assert.equal(second.name, "NGUYEN VAN LONG");
});

test("persona helper rejects unsupported types and empty demo identifiers", () => {
  assert.throws(() => createDemoPersona("unknown", () => 0, "id"), RangeError);
  assert.throws(() => createDemoPersona("domestic", () => 0, "---"), RangeError);
});

test("explicit persona nationality remains compatible after editing the birth date", () => {
  assert.equal(createDemoRegistration("2004-03-12", () => 0, "foreign"), "040312-7000000");
  assert.equal(createDemoRegistration("2004-03-12", () => 0, "domestic"), "040312-3000000");
});

for (const [birth, kind, male, female] of [
  ["1891-04-18", "domestic", 9, 0],
  ["1994-03-12", "domestic", 1, 2], ["2004-03-12", "domestic", 3, 4],
  ["1994-03-12", "foreign", 5, 6], ["2004-03-12", "foreign", 7, 8],
]) {
  for (const [sex, code] of [["male", male], ["female", female]]) {
    test(`explicit ${kind} ${sex} ${birth} uses code ${code}`, () => {
      const number = createDemoRegistration(birth, () => 0.000042, kind, sex);
      assert.equal(number, `${birth.replaceAll("-", "").slice(2)}-${code}000042`);
    });
  }
}

test("six trailing digits change independently of the fixed persona sex code", () => {
  const first = createDemoRegistration("1994-03-12", () => 0, "foreign", "male");
  const second = createDemoRegistration("1994-03-12", () => 0.999999, "foreign", "male");
  assert.equal(first, "940312-5000000");
  assert.equal(second, "940312-5999999");
  assert.equal(first.slice(0, 8), second.slice(0, 8));
  assert.notEqual(first.slice(8), second.slice(8));
});

test("display masking does not change the full value used by JSON", () => {
  const persona = createDemoPersona("foreign", () => 0.49, "json-export-test");
  assert.match(maskDemoRegistration(persona.registration_number), /^\d{6}-6\*{6}$/);
  assert.equal(JSON.parse(JSON.stringify(persona)).registration_number, "900905-6490000");
});
