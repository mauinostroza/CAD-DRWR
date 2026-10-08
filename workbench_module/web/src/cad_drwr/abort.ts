/**
 * `lib_client.get/post` y `sapRequestRaw` no aceptan `AbortSignal`: la petición HTTP sigue su curso,
 * pero la promesa que ve el llamador se rechaza al abortar (el resultado tardío se descarta).
 */
export function conAbort<T>(promesa: Promise<T>, signal?: AbortSignal): Promise<T> {
  if (!signal) return promesa
  return new Promise<T>((resolve, reject) => {
    const abortar = () => reject(new DOMException('Cancelado', 'AbortError'))
    if (signal.aborted) return abortar()
    signal.addEventListener('abort', abortar, { once: true })
    promesa.then(resolve, reject).finally(() => signal.removeEventListener('abort', abortar))
  })
}
