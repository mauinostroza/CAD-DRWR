import '@testing-library/jest-dom/vitest'

// jsdom no implementa <dialog>.showModal()/close() (usados por Dialog.tsx vía
// Foundations' fd-dialog) — sin este polyfill cualquier prueba que abra un
// diálogo modal explota con "showModal is not a function".
if (typeof HTMLDialogElement !== 'undefined') {
  if (!HTMLDialogElement.prototype.showModal) {
    HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
      this.setAttribute('open', '')
    }
  }
  // El Report Builder flotante (report/ReportBuilderWindow.tsx) abre su panel con
  // show() a propósito, no showModal(), para no competir por la capa superior del
  // navegador con un <dialog> modal de Fundaciones — jsdom tampoco implementa esta.
  if (!HTMLDialogElement.prototype.show) {
    HTMLDialogElement.prototype.show = function (this: HTMLDialogElement) {
      this.setAttribute('open', '')
    }
  }
  if (!HTMLDialogElement.prototype.close) {
    HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
      this.removeAttribute('open')
    }
  }
}
