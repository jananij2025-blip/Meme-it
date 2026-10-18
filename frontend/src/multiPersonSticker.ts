
export type StickerCharacter = {
  person_index: number;
  label: string;
  x: number;
  y: number;
};

const SIZE = 512;

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function makeCanvas(width: number, height: number) {
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(width));
  canvas.height = Math.max(1, Math.round(height));
  return canvas;
}

function getContext(canvas: HTMLCanvasElement) {
  const ctx = canvas.getContext("2d", {
    willReadFrequently: true,
  });

  if (!ctx) throw new Error("Canvas unavailable.");
  return ctx;
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Image could not load."));
    image.src = url;
  });
}

function trimTransparent(source: HTMLCanvasElement) {
  const ctx = getContext(source);
  const { width, height } = source;
  const data = ctx.getImageData(0, 0, width, height).data;

  let minX = width;
  let minY = height;
  let maxX = -1;
  let maxY = -1;

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const alpha = data[(y * width + x) * 4 + 3];
      if (alpha < 40) continue;

      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
    }
  }

  if (maxX < 0) return source;

  const result = makeCanvas(
    maxX - minX + 1,
    maxY - minY + 1
  );

  getContext(result).drawImage(
    source,
    minX,
    minY,
    result.width,
    result.height,
    0,
    0,
    result.width,
    result.height
  );

  return result;
}

function cropPerson(
  image: HTMLImageElement,
  person: StickerCharacter,
  people: StickerCharacter[]
) {
  
  // A rectangular crop is not person segmentation.
  // Check whether the supplied image has transparency.
  const transparencyCanvas = makeCanvas(
    image.naturalWidth,
    image.naturalHeight
  );

  const transparencyCtx = getContext(transparencyCanvas);

  transparencyCtx.drawImage(image, 0, 0);

  const pixels = transparencyCtx.getImageData(
    0,
    0,
    transparencyCanvas.width,
    transparencyCanvas.height
  ).data;

  let transparentPixels = 0;

  for (let i = 3; i < pixels.length; i += 4) {
    if (pixels[i] < 240) {
      transparentPixels++;
    }
  }

  if (transparentPixels === 0) {
    throw new Error(
      "The photo background was not removed. " +
      "Please try another image or check the " +
      "background-removal service."
    );
  }

  const width = image.naturalWidth;
  const height = image.naturalHeight;

  const centerX = clamp(person.x, 0, 1) * width;
  const centerY = clamp(person.y, 0, 1) * height;

  const distances = people
    .filter(p => p.person_index !== person.person_index)
    .map(p => Math.abs(p.x - person.x) * width)
    .filter(d => d > 1);

  const nearest = distances.length
    ? Math.min(...distances)
    : width * 0.5;

  const cropWidth = Math.min(
    width,
    clamp(nearest * 0.95, width * 0.16, width * 0.5)
  );

  const cropHeight = Math.min(
    height,
    Math.max(cropWidth * 1.7, height * 0.42)
  );

  const left = clamp(
    centerX - cropWidth / 2,
    0,
    width - cropWidth
  );

  const top = clamp(
    centerY - cropHeight * 0.22,
    0,
    height - cropHeight
  );

  const canvas = makeCanvas(cropWidth, cropHeight);

  getContext(canvas).drawImage(
    image,
    left,
    top,
    cropWidth,
    cropHeight,
    0,
    0,
    canvas.width,
    canvas.height
  );

  return trimTransparent(canvas);
}

function wrapText(
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number
) {
  const lines: string[] = [];
  let current = "";

  for (const word of text.trim().split(/\s+/)) {
    const next = current ? `${current} ${word}` : word;

    if (current && ctx.measureText(next).width > maxWidth) {
      lines.push(current);
      current = word;
    } else {
      current = next;
    }
  }

  if (current) lines.push(current);
  return lines;
}

function getCaptionLayout(
  ctx: CanvasRenderingContext2D,
  caption: string
) {
  for (let size = 30; size >= 12; size--) {
    ctx.font = `900 ${size}px Arial, sans-serif`;

    const lines = wrapText(ctx, caption, 455);

    if (
      lines.length <= 5 &&
      lines.every(line => ctx.measureText(line).width <= 455)
    ) {
      return {
        lines,
        size,
        lineHeight: size + 6,
        height: lines.length * (size + 6),
      };
    }
  }

  throw new Error("Please shorten the caption.");
}

function drawCaption(
  ctx: CanvasRenderingContext2D,
  caption: string,
  top: number
) {
  const layout = getCaptionLayout(ctx, caption);

  ctx.save();
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.lineJoin = "round";
  ctx.font = `900 ${layout.size}px Arial, sans-serif`;
  ctx.strokeStyle = "white";
  ctx.fillStyle = "#151515";
  ctx.lineWidth = Math.max(4, layout.size * 0.25);

  layout.lines.forEach((line, index) => {
    const y = top + (index + 0.5) * layout.lineHeight;
    ctx.strokeText(line, SIZE / 2, y, 455);
    ctx.fillText(line, SIZE / 2, y, 455);
  });

  ctx.restore();
}

function drawPerson(
  ctx: CanvasRenderingContext2D,
  image: HTMLCanvasElement,
  x: number,
  y: number,
  width: number,
  height: number
) {
  const outline = makeCanvas(SIZE, SIZE);
  const outlineCtx = getContext(outline);

  for (let dx = -3; dx <= 3; dx++) {
    for (let dy = -3; dy <= 3; dy++) {
      if (dx * dx + dy * dy > 9) continue;

      outlineCtx.drawImage(
        image,
        x + dx,
        y + dy,
        width,
        height
      );
    }
  }

  outlineCtx.globalCompositeOperation = "source-in";
  outlineCtx.fillStyle = "#ffffff";
  outlineCtx.fillRect(0, 0, SIZE, SIZE);

  ctx.drawImage(outline, 0, 0);
  ctx.drawImage(image, x, y, width, height);
}

function drawLabel(
  ctx: CanvasRenderingContext2D,
  label: string,
  centerX: number,
  centerY: number,
  maxWidth: number
) {
  const text = label.trim().toUpperCase();
  let size = 20;

  while (size > 10) {
    ctx.font = `900 ${size}px Arial, sans-serif`;

    if (ctx.measureText(text).width <= maxWidth - 18) {
      break;
    }

    size--;
  }

  const width = Math.min(
    maxWidth,
    ctx.measureText(text).width + 20
  );
  const height = size + 17;

  ctx.save();
  ctx.fillStyle = "#c4ff70";
  ctx.strokeStyle = "#151515";
  ctx.lineWidth = 2;

  ctx.beginPath();
  ctx.roundRect(
    centerX - width / 2,
    centerY - height / 2,
    width,
    height,
    8
  );
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = "#151515";
  ctx.font = `900 ${size}px Arial, sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, centerX, centerY, width - 14);
  ctx.restore();
}

function getRows(count: number): number[][] {
  if (count <= 3) {
    return [Array.from({ length: count }, (_, i) => i)];
  }

  if (count === 4) return [[0, 1], [2, 3]];

  return [[0, 1, 2], [3, 4]];
}

export async function createMultiPersonSticker(
  cutoutUrl: string,
  caption: string,
  characters: StickerCharacter[]
): Promise<string> {
  if (!caption.trim()) throw new Error("Enter a caption.");
  if (!characters.length) throw new Error("No people selected.");
  if (characters.length > 5) {
    throw new Error("A maximum of five people is supported.");
  }

  const image = await loadImage(cutoutUrl);
  const canvas = makeCanvas(SIZE, SIZE);
  const ctx = getContext(canvas);

  const layout = getCaptionLayout(ctx, caption);
  const captionTop = SIZE - layout.height - 16;

  const sorted = [...characters].sort((a, b) => a.x - b.x);
  const cutouts = sorted.map(person =>
    cropPerson(image, person, sorted)
  );

  const rows = getRows(cutouts.length);
  const availableHeight = captionTop - 30;
  const rowHeight = availableHeight / rows.length;

  rows.forEach((row, rowIndex) => {
    const cellWidth = 468 / row.length;
    const rowTop = 18 + rowIndex * rowHeight;
    const labelY = rowTop + 17;
    const imageTop = rowTop + 43;
    const imageBottom = rowTop + rowHeight - 5;

    row.forEach((index, columnIndex) => {
      const person = cutouts[index];
      const centerX = 22 + cellWidth * (columnIndex + 0.5);

      const maxWidth = cellWidth - 12;
      const maxHeight = Math.max(20, imageBottom - imageTop);

      const scale = Math.min(
        maxWidth / person.width,
        maxHeight / person.height
      );

      const width = person.width * scale;
      const height = person.height * scale;

      drawPerson(
        ctx,
        person,
        centerX - width / 2,
        imageBottom - height,
        width,
        height
      );

      drawLabel(
        ctx,
        sorted[index].label,
        centerX,
        labelY,
        cellWidth - 8
      );
    });
  });

  drawCaption(ctx, caption, captionTop);

  return canvas.toDataURL("image/png");
}

// Crops a chosen person out of the background-removed image.
// Returns a transparent PNG data URL.
export async function isolateSelectedPerson(
  cutoutUrl: string,
  selected: StickerCharacter,
  allPeople: StickerCharacter[]
): Promise<string> {
  const image = await loadImage(cutoutUrl);

  const cutout = cropPerson(
    image,
    selected,
    allPeople
  );

  return cutout.toDataURL("image/png");
}
