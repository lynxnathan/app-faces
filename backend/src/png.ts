const MAX_ICON_BYTES = 256 * 1024;
const MAX_ICON_DIMENSION = 512;

export async function normalizePng(data: Uint8Array): Promise<Uint8Array> {
  const fail = (): never => {
    throw new Error(
      "Expected a valid non-interlaced RGB/RGBA PNG, 1–512px, at most 256KiB",
    );
  };
  if (
    data.length > MAX_ICON_BYTES ||
    data.length < 57 ||
    ![137, 80, 78, 71, 13, 10, 26, 10].every((v, i) => data[i] === v)
  )
    fail();
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
  const kept: Uint8Array[] = [data.slice(0, 8)];
  const compressed: Uint8Array[] = [];
  let offset = 8,
    width = 0,
    height = 0,
    channels = 0,
    ended = false,
    sawData = false,
    closedData = false;
  while (offset + 12 <= data.length) {
    const length = view.getUint32(offset);
    if (length > data.length - offset - 12) fail();
    const type = String.fromCharCode(...data.slice(offset + 4, offset + 8));
    const body = data.slice(offset + 8, offset + 8 + length);
    if (
      crc32(data.subarray(offset + 4, offset + 8 + length)) !==
      view.getUint32(offset + 8 + length)
    )
      fail();
    if (offset === 8 && type !== "IHDR") fail();
    if (type === "IHDR") {
      if (offset !== 8 || length !== 13) fail();
      width = view.getUint32(offset + 8);
      height = view.getUint32(offset + 12);
      channels = body[9] === 6 ? 4 : body[9] === 2 ? 3 : 0;
      if (
        !width ||
        !height ||
        width > MAX_ICON_DIMENSION ||
        height > MAX_ICON_DIMENSION ||
        !channels ||
        body[8] !== 8 ||
        body[10] !== 0 ||
        body[11] !== 0 ||
        body[12] !== 0
      )
        fail();
    } else if (type === "IDAT") {
      if (closedData) fail();
      compressed.push(body);
      sawData = true;
    } else if (type === "IEND") {
      if (length !== 0 || !sawData) fail();
      ended = true;
    } else {
      if (sawData) closedData = true;

      if (
        type[0] === type[0]?.toUpperCase() ||
        ["acTL", "fcTL", "fdAT"].includes(type)
      )
        fail();
    }
    if (["IHDR", "IDAT", "IEND"].includes(type))
      kept.push(data.slice(offset, offset + 12 + length));
    offset += 12 + length;
    if (ended) break;
  }
  if (!ended || offset !== data.length) fail();
  const packed = concat(compressed);
  const expected = (width * channels + 1) * height;
  const reader = new Blob([packed])
    .stream()
    .pipeThrough(new DecompressionStream("deflate"))
    .getReader();
  let inflated = 0;
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      const stride = width * channels + 1;
      for (
        let i = (stride - (inflated % stride)) % stride;
        i < chunk.value.length;
        i += stride
      ) {
        if ((chunk.value[i] ?? 255) > 4) fail();
      }
      inflated += chunk.value.length;
      if (inflated > expected) {
        await reader.cancel();
        fail();
      }
    }
  } catch {
    fail();
  }
  if (inflated !== expected) fail();
  return concat(kept);
}
function concat(parts: Uint8Array[]): Uint8Array<ArrayBuffer> {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let offset = 0;
  for (const p of parts) {
    out.set(p, offset);
    offset += p.length;
  }
  return out;
}
const crcTable = Uint32Array.from({ length: 256 }, (_, index) => {
  let crc = index;
  for (let bit = 0; bit < 8; bit++)
    crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
  return crc >>> 0;
});
function crc32(data: Uint8Array): number {
  let crc = 0xffffffff;
  for (const byte of data) crc = (crc >>> 8) ^ crcTable[(crc ^ byte) & 255]!;
  return (crc ^ 0xffffffff) >>> 0;
}
