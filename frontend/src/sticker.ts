
export async function createSticker(
  photoUrl: string,
  caption: string
): Promise<string> {
  const SIZE = 512;

  const canvas = document.createElement("canvas");
  canvas.width = SIZE;
  canvas.height = SIZE;

  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("Canvas is not supported.");
  }

  const image = new Image();
  image.src = photoUrl;
  await image.decode();

  const sourceCanvas = document.createElement("canvas");
  sourceCanvas.width = image.naturalWidth;
  sourceCanvas.height = image.naturalHeight;

  const sourceCtx = sourceCanvas.getContext("2d");
  if (!sourceCtx) {
    throw new Error("Canvas is not supported.");
  }

  sourceCtx.drawImage(image, 0, 0);

  const pixels = sourceCtx.getImageData(
    0,
    0,
    sourceCanvas.width,
    sourceCanvas.height
  );

  let minX = sourceCanvas.width;
  let minY = sourceCanvas.height;
  let maxX = -1;
  let maxY = -1;

  for (let y = 0; y < sourceCanvas.height; y++) {
    for (let x = 0; x < sourceCanvas.width; x++) {
      const alpha =
        pixels.data[
          (y * sourceCanvas.width + x) * 4 + 3
        ];

      if (alpha > 30) {
        minX = Math.min(minX, x);
        minY = Math.min(minY, y);
        maxX = Math.max(maxX, x);
        maxY = Math.max(maxY, y);
      }
    }
  }

  if (maxX < minX || maxY < minY) {
    throw new Error("No visible subject found.");
  }

  const cropWidth = maxX - minX + 1;
  const cropHeight = maxY - minY + 1;

  // Reserve the bottom part for the caption.
  const IMAGE_TOP = 16;
  const IMAGE_BOTTOM = 340;
  const IMAGE_MAX_WIDTH = 460;
  const IMAGE_MAX_HEIGHT = IMAGE_BOTTOM - IMAGE_TOP;

  const scale = Math.min(
    IMAGE_MAX_WIDTH / cropWidth,
    IMAGE_MAX_HEIGHT / cropHeight
  );

  const width = cropWidth * scale;
  const height = cropHeight * scale;

  const personX = (SIZE - width) / 2;
  const personY = IMAGE_TOP + IMAGE_MAX_HEIGHT - height;

  const personCanvas = document.createElement("canvas");
  personCanvas.width = SIZE;
  personCanvas.height = SIZE;

  const personCtx = personCanvas.getContext("2d");
  if (!personCtx) {
    throw new Error("Canvas is not supported.");
  }

  personCtx.drawImage(
    image,
    minX,
    minY,
    cropWidth,
    cropHeight,
    personX,
    personY,
    width,
    height
  );

  // Create the white sticker outline.
  const silhouette = document.createElement("canvas");
  silhouette.width = SIZE;
  silhouette.height = SIZE;

  const silhouetteCtx = silhouette.getContext("2d");
  if (!silhouetteCtx) {
    throw new Error("Canvas is not supported.");
  }

  silhouetteCtx.drawImage(personCanvas, 0, 0);
  silhouetteCtx.globalCompositeOperation = "source-in";
  silhouetteCtx.fillStyle = "#ffffff";
  silhouetteCtx.fillRect(0, 0, SIZE, SIZE);

  const outlineRadius = 5;

  for (
    let dx = -outlineRadius;
    dx <= outlineRadius;
    dx++
  ) {
    for (
      let dy = -outlineRadius;
      dy <= outlineRadius;
      dy++
    ) {
      if (
        dx * dx + dy * dy <=
        outlineRadius * outlineRadius
      ) {
        ctx.drawImage(silhouette, dx, dy);
      }
    }
  }

  ctx.drawImage(personCanvas, 0, 0);

  // Caption area.
  const TEXT_TOP = 355;
  const TEXT_BOTTOM = 500;
  const MAX_TEXT_WIDTH = 460;
  const MAX_LINES = 4;

  const words = caption.trim().split(/\s+/);

  function wrapText(fontSize: number): string[] {
    ctx!.font = `900 ${fontSize}px Arial`;

    const lines: string[] = [];
    let current = "";

    for (const word of words) {
      const candidate = current
        ? `${current} ${word}`
        : word;

      if (
        ctx!.measureText(candidate).width <=
        MAX_TEXT_WIDTH
      ) {
        current = candidate;
      } else {
        if (current) {
          lines.push(current);
        }

        current = word;
      }
    }

    if (current) {
      lines.push(current);
    }

    return lines;
  }

  let fontSize = 38;
  let lines = wrapText(fontSize);

  while (fontSize > 12) {
    const lineHeight = fontSize * 1.12;

    const fitsWidth = lines.every(
      line =>
        ctx.measureText(line).width <= MAX_TEXT_WIDTH
    );

    const fitsHeight =
      lines.length <= MAX_LINES &&
      lines.length * lineHeight <=
        TEXT_BOTTOM - TEXT_TOP;

    if (fitsWidth && fitsHeight) {
      break;
    }

    fontSize -= 1;
    lines = wrapText(fontSize);
  }

  ctx.font = `900 ${fontSize}px Arial`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.lineJoin = "round";

  const lineHeight = fontSize * 1.12;
  const totalHeight = lines.length * lineHeight;

  const startY =
    TEXT_TOP +
    (TEXT_BOTTOM - TEXT_TOP - totalHeight) / 2 +
    lineHeight / 2;

  lines.forEach((line, index) => {
    const y = startY + index * lineHeight;

    ctx.lineWidth = 7;
    ctx.strokeStyle = "#000000";
    ctx.fillStyle = "#ffffff";

    ctx.strokeText(line, SIZE / 2, y, MAX_TEXT_WIDTH);
    ctx.fillText(line, SIZE / 2, y, MAX_TEXT_WIDTH);
  });

  return canvas.toDataURL("image/png");
}
