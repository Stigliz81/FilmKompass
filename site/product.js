'use strict';
const productViewer = document.querySelector('body.product dialog');
if (productViewer) {
  const actual = productViewer.querySelector('.actual-size');
  actual.addEventListener('click', () => {
    const enabled = productViewer.classList.toggle('show-actual');
    actual.textContent = enabled ? 'An Fenster anpassen' : 'Originalgröße anzeigen';
  });
  productViewer.addEventListener('close', () => {
    productViewer.classList.remove('show-actual');
    actual.textContent = 'Originalgröße anzeigen';
  });
}
