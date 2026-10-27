/* Field guidance complements the mandatory server-side identity validation. */
(() => {
  const type = document.querySelector('[data-identity-type]');
  if (!type) return;
  const number = document.querySelector('[data-identity-number]');
  const help = document.querySelector('[data-identity-help]');
  const country = document.querySelector('[data-passport-country]');
  function update() {
    const passport = type.value === 'PASSPORT';
    country.hidden = !passport;
    country.querySelector('input').disabled = !passport;
    country.querySelector('input').required = passport;
    number.inputMode = passport ? 'text' : 'numeric';
    number.maxLength = passport ? 20 : type.value === 'NISN' ? 10 : 16;
    number.pattern = passport ? '[A-Za-z0-9]{5,20}' : `[0-9]{${number.maxLength}}`;
    help.textContent = passport ? '5–20 huruf atau angka, sesuai paspor.' : `${number.maxLength} angka, sesuai ${type.value === 'NIK' ? 'KTP' : 'NISN'}.`;
    number.placeholder = passport ? 'Nomor paspor / Passport number' : `Masukkan ${number.maxLength} angka`;
  }
  type.addEventListener('change', update); update();
})();
