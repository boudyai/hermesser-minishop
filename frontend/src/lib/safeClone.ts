type JsonRecord = Record<string, unknown>;

function cloneJsonFallback(value: unknown, ancestors = new WeakSet<object>()): unknown {
  if (value === null) return null;

  const valueType = typeof value;
  if (valueType === "string" || valueType === "number" || valueType === "boolean") {
    return value;
  }
  if (valueType === "bigint") return String(value);
  if (valueType !== "object") return undefined;

  const objectValue = value as object;
  if (ancestors.has(objectValue)) return undefined;
  if (objectValue instanceof Date) return objectValue.toISOString();

  ancestors.add(objectValue);

  const maybeJsonValue = objectValue as { toJSON?: unknown };
  if (typeof maybeJsonValue.toJSON === "function") {
    try {
      const result = cloneJsonFallback(maybeJsonValue.toJSON(), ancestors);
      ancestors.delete(objectValue);
      return result;
    } catch (_error) {
      void _error;
    }
  }

  if (Array.isArray(objectValue)) {
    const cloned = objectValue.map((item) => {
      const result = cloneJsonFallback(item, ancestors);
      return result === undefined ? null : result;
    });
    ancestors.delete(objectValue);
    return cloned;
  }

  const prototype = Object.getPrototypeOf(objectValue);
  if (prototype !== Object.prototype && prototype !== null) {
    ancestors.delete(objectValue);
    return undefined;
  }

  const cloned: JsonRecord = {};
  for (const [key, item] of Object.entries(objectValue)) {
    const result = cloneJsonFallback(item, ancestors);
    if (result !== undefined) cloned[key] = result;
  }
  ancestors.delete(objectValue);
  return cloned;
}

export function structuredCloneSafe<T>(value: T): T {
  if (typeof structuredClone === "function") {
    try {
      return structuredClone(value);
    } catch (_error) {
      void _error;
    }
  }

  try {
    const text = JSON.stringify(value);
    return text === undefined ? (undefined as T) : (JSON.parse(text) as T);
  } catch (_error) {
    void _error;
  }

  return cloneJsonFallback(value) as T;
}
