export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function optionalProperty<K extends PropertyKey, V>(
  key: K,
  value: V | undefined,
): { [P in K]?: V } {
  const output: { [P in K]?: V } = {};
  if (value !== undefined) {
    output[key] = value;
  }
  return output;
}
