// Tiny observable: a value plus subscribers. Copied out of the host app so the
// confirm gate can publish its pending request without pulling in a framework.

type Listener<T> = (value: T) => void;

export class Signal<T> {
  private listeners = new Set<Listener<T>>();
  value: T;
  constructor(initial: T) {
    this.value = initial;
  }
  set(value: T): void {
    this.value = value;
    this.listeners.forEach((l) => l(value));
  }
  subscribe(fn: Listener<T>): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }
}
