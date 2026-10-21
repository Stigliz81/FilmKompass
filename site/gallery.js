'use strict';
const viewer = document.querySelector('dialog');
if (viewer && typeof viewer.showModal === 'function') {
  const image = viewer.querySelector('img');
  const caption = viewer.querySelector('p');
  for (const link of document.querySelectorAll('a.zoom')) {
    link.addEventListener('click', event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      image.src = link.href;
      image.alt = link.querySelector('img').alt;
      caption.textContent = image.alt;
      viewer.showModal();
    });
  }
  viewer.querySelector('button').addEventListener('click', () => viewer.close());
  viewer.addEventListener('click', event => { if (event.target === viewer) viewer.close(); });
}

const support = document.querySelector('#unterstuetzen details');
for (const link of document.querySelectorAll('a[href="#unterstuetzen"]')) {
  link.addEventListener('click', () => { if (support) support.open = true; });
}
for (const button of document.querySelectorAll('.copy-payment')) {
  button.addEventListener('click', async () => {
    const card = button.closest('.payment-card');
    const field = card.querySelector('input');
    const feedback = card.querySelector('[role="status"]');
    try {
      await navigator.clipboard.writeText(field.value);
      feedback.textContent = 'Zahlungsziel kopiert.';
    } catch {
      field.focus();
      field.select();
      feedback.textContent = 'Bitte das markierte Zahlungsziel manuell kopieren.';
    }
  });
}
