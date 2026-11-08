'use strict';
for (const button of document.querySelectorAll('.copy-prompt')) {
  const source = document.getElementById(button.dataset.copyTarget);
  if (!source) continue;
  button.disabled = false;
  button.addEventListener('click', async () => {
    const text = source.textContent.trim();
    const status = button.closest('.prompt-card').querySelector('[role="status"]');
    let copied = false;
    try {
      await navigator.clipboard.writeText(text);
      copied = true;
    } catch {
      const field = document.createElement('textarea');
      field.value = text;
      field.readOnly = true;
      field.style.cssText = 'position:fixed;top:0;left:0;opacity:0;pointer-events:none';
      document.body.append(field);
      try {
        field.focus();
        field.select();
        field.setSelectionRange(0, text.length);
        copied = document.execCommand('copy');
      } catch {
        copied = false;
      } finally {
        field.remove();
        button.focus({preventScroll: true});
      }
    }
    if (copied) {
      status.textContent = 'Prompt kopiert.';
    } else {
      source.focus({preventScroll: true});
      const range = document.createRange();
      range.selectNodeContents(source);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      status.textContent = 'Kopieren wurde blockiert. Bitte den markierten Prompt manuell kopieren.';
    }
  });
}
