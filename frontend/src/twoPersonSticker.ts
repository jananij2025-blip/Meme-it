
const SIZE = 512;

type Bounds = {
  x: number;
  y: number;
  width: number;
  height: number;
};

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();

    image.onload = () => resolve(image);
    image.onerror = () =>
      reject(new Error("Could not load sticker image."));

    image.src = src;
  });
}

function getAlphaBounds(
  image: HTMLImageElement,
  minAlpha = 35
): Bounds {
  const canvas = document.createElement("canvas");
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;

  const ctx = canvas.getContext("2d", {
    willReadFrequently: true,
  });

  if (!ctx) {
    throw new Error("Canvas is not available.");
  }

  ctx.drawImage(image, 0, 0);

  const pixels = ctx.getImageData(
    0,
    0,
    canvas.width,
    canvas.height
  ).data;

  let minX = canvas.width;
  let minY = canvas.height;
  let maxX = -1;
  let maxY = -1;

  for (let y = 0; y < canvas.height; y++) {
    for (let x = 0; x < canvas.width; x++) {
      const alpha =
        pixels[(y * canvas.width + x) * 4 + 3];

      if (alpha >= minAlpha) {
        minX = Math.min(minX, x);
        minY = Math.min(minY, y);
        maxX = Math.max(maxX, x);
        maxY = Math.max(maxY, y);
      }
    }
  }

  if (maxX < minX || maxY < minY) {
    throw new Error("No visible subject found in image.");
  }

  return {
    x: minX,
    y: minY,
    width: maxX - minX + 1,
    height: maxY - minY + 1,
  };
}

function wrapText(
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number
): string[] {
  const words = text.trim().split(/\s+/);
  const lines: string[] = [];
  let current = "";

  for (const word of words) {
    const test = current ? `${current} ${word}` : word;

    if (
      ctx.measureText(test).width <= maxWidth ||
      !current
    ) {
      current = test;
    } else {
      lines.push(current);
      current = word;
    }
  }

  if (current) lines.push(current);

  return lines;
}

function drawOutlinedText(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  fontSize: number,
  maxWidth: number
) {
  ctx.save();

  ctx.font = `900 ${fontSize}px Arial, sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.lineJoin = "round";

  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = Math.max(4, fontSize * 0.24);
  ctx.strokeText(text, x, y, maxWidth);

  ctx.fillStyle = "#151515";
  ctx.fillText(text, x, y, maxWidth);

  ctx.restore();
}

function measureCaptionHeight(
  ctx: CanvasRenderingContext2D,
  caption: string
) {
  const maxWidth = 454;
  const maxLines = 5;

  for (let fontSize = 31; fontSize >= 15; fontSize--) {
    ctx.font = `900 ${fontSize}px Arial, sans-serif`;

    const lines = wrapText(ctx, caption, maxWidth);

    if (
      lines.length <= maxLines &&
      lines.every(
        (line) => ctx.measureText(line).width <= maxWidth
      )
    ) {
      return {
        fontSize,
        lines,
        lineHeight: fontSize + 7,
        height: lines.length * (fontSize + 7),
      };
    }
  }

  throw new Error(
    "Caption is too long for the sticker. Shorten it."
  );
}

function drawCaption(
  ctx: CanvasRenderingContext2D,
  caption: string,
  top: number
) {
  const layout = measureCaptionHeight(ctx, caption);

  const firstY =
    top + layout.lineHeight / 2;

  layout.lines.forEach((line, index) => {
    drawOutlinedText(
      ctx,
      line,
      SIZE / 2,
      firstY + index * layout.lineHeight,
      layout.fontSize,
      454
    );
  });
}

function makeWhiteOutline(
  source: HTMLCanvasElement,
  radius: number
): HTMLCanvasElement {
  const outlined = document.createElement("canvas");
  outlined.width = SIZE;
  outlined.height = SIZE;

  const ctx = outlined.getContext("2d");

  if (!ctx) {
    throw new Error("Could not create outline.");
  }

  for (let dx = -radius; dx <= radius; dx++) {
    for (let dy = -radius; dy <= radius; dy++) {
      if (dx * dx + dy * dy > radius * radius) {
        continue;
      }

      ctx.drawImage(source, dx, dy);
    }
  }

  ctx.globalCompositeOperation = "source-in";
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, SIZE, SIZE);

  ctx.globalCompositeOperation = "source-over";
  ctx.drawImage(source, 0, 0);

  return outlined;
}

function drawLabel(
  ctx: CanvasRenderingContext2D,
  label: string,
  centerX: number,
  centerY: number,
  maxBoxWidth = 216
) {
  const text = label.trim().toUpperCase();

  let fontSize = 23;

  while (fontSize > 12) {
    ctx.font = `900 ${fontSize}px Arial, sans-serif`;

    if (
      ctx.measureText(text).width <= maxBoxWidth - 22
    ) {
      break;
    }

    fontSize--;
  }

  const maxTextWidth = maxBoxWidth - 22;

  ctx.font = `900 ${fontSize}px Arial, sans-serif`;

  const textWidth = Math.min(
    ctx.measureText(text).width,
    maxTextWidth
  );

  const boxWidth = Math.min(
    maxBoxWidth,
    textWidth + 24
  );

  const boxHeight = 37;

  const safeX = Math.max(
    boxWidth / 2 + 8,
    Math.min(
      SIZE - boxWidth / 2 - 8,
      centerX
    )
  );

  ctx.save();

  ctx.fillStyle = "#c4ff70";
  ctx.beginPath();

  ctx.roundRect(
    safeX - boxWidth / 2,
    centerY - boxHeight / 2,
    boxWidth,
    boxHeight,
    10
  );

  ctx.fill();

  ctx.fillStyle = "#151515";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.font = `900 ${fontSize}px Arial, sans-serif`;

  ctx.fillText(
    text,
    safeX,
    centerY,
    maxTextWidth
  );

  ctx.restore();
}

/**
 * Estimate the upper visible subject area in one half
 * of the rendered cutout.
 *
 * This is alpha-based positioning, not face detection.
 */
function findPersonAnchor(
  canvas: HTMLCanvasElement,
  side: "left" | "right",
  fallbackX: number,
  fallbackTop: number
) {
  const ctx = canvas.getContext("2d", {
    willReadFrequently: true,
  });

  if (!ctx) {
    return {
      x: fallbackX,
      top: fallbackTop,
    };
  }

  const width = canvas.width;
  const height = canvas.height;

  const pixels = ctx.getImageData(
    0,
    0,
    width,
    height
  ).data;

  const startX = side === "left" ? 0 : SIZE / 2;
  const endX = side === "left" ? SIZE / 2 : SIZE;

  // Look for the top of the person, ignoring tiny artifacts.
  const rowThreshold = 8;
  let top = -1;

  for (let y = 0; y < height; y++) {
    let visible = 0;

    for (let x = startX; x < endX; x++) {
      const alpha = pixels[
        (y * width + x) * 4 + 3
      ];

      if (alpha > 100) visible++;
    }

    if (visible >= rowThreshold) {
      top = y;
      break;
    }
  }

  if (top < 0) {
    return {
      x: fallbackX,
      top: fallbackTop,
    };
  }

  // Estimate the horizontal centre near the head.
  const sampleBottom = Math.min(
    height,
    top + 90
  );

  let sumX = 0;
  let count = 0;

  for (let y = top; y < sampleBottom; y++) {
    for (let x = startX; x < endX; x++) {
      const alpha = pixels[
        (y * width + x) * 4 + 3
      ];

      if (alpha > 140) {
        sumX += x;
        count++;
      }
    }
  }

  return {
    x: count > 0 ? sumX / count : fallbackX,
    top,
  };
}

export async function createTwoPersonSticker(
  cutoutUrl: string,
  leftLabel: string,
  rightLabel: string,
  caption: string
): Promise<string> {
  if (
    !leftLabel.trim() ||
    !rightLabel.trim() ||
    !caption.trim()
  ) {
    throw new Error(
      "Both person labels and a caption are required."
    );
  }

  const image = await loadImage(cutoutUrl);
  const bounds = getAlphaBounds(image);

  const canvas = document.createElement("canvas");
  canvas.width = SIZE;
  canvas.height = SIZE;

  const ctx = canvas.getContext("2d");

  if (!ctx) {
    throw new Error("Canvas is not available.");
  }

  // Transparent canvas by default.
  ctx.clearRect(0, 0, SIZE, SIZE);

  // Work out how much space the caption needs FIRST.
  const captionLayout = measureCaptionHeight(
    ctx,
    caption
  );

  const captionBottom = SIZE - 17;
  const captionTop =
    captionBottom - captionLayout.height;

  // Keep a gap between subjects and caption.
  const imageBottom = captionTop - 20;

  // Reserve room for labels above subjects.
  const imageTop = 58;

  const imageArea = {
    x: 12,
    y: imageTop,
    width: SIZE - 24,
    height: Math.max(80, imageBottom - imageTop),
  };

  const scale = Math.min(
    imageArea.width / bounds.width,
    imageArea.height / bounds.height
  );

  const drawWidth = bounds.width * scale;
  const drawHeight = bounds.height * scale;

  const drawX =
    imageArea.x +
    (imageArea.width - drawWidth) / 2;

  // Align subjects to the bottom of their allocated area.
  const drawY =
    imageBottom - drawHeight;

  const subjectCanvas = document.createElement("canvas");
  subjectCanvas.width = SIZE;
  subjectCanvas.height = SIZE;

  const subjectCtx = subjectCanvas.getContext("2d");

  if (!subjectCtx) {
    throw new Error("Could not prepare cutout.");
  }

  subjectCtx.drawImage(
    image,
    bounds.x,
    bounds.y,
    bounds.width,
    bounds.height,
    drawX,
    drawY,
    drawWidth,
    drawHeight
  );

  const outlined = makeWhiteOutline(
    subjectCanvas,
    4
  );

  ctx.drawImage(outlined, 0, 0);

  // Estimate where each person starts in the rendered image.
  const leftAnchor = findPersonAnchor(
    subjectCanvas,
    "left",
    128,
    drawY
  );

  const rightAnchor = findPersonAnchor(
    subjectCanvas,
    "right",
    384,
    drawY
  );

  // Place labels close to the heads, not at canvas top.
  // If the people are close to the top, use a safe margin.
  const labelHeight = 37;
  const labelGap = 9;

  const leftLabelY = Math.max(
    labelHeight / 2 + 5,
    leftAnchor.top - labelGap - labelHeight / 2
  );

  const rightLabelY = Math.max(
    labelHeight / 2 + 5,
    rightAnchor.top - labelGap - labelHeight / 2
  );

  drawLabel(
    ctx,
    leftLabel,
    leftAnchor.x,
    leftLabelY,
    216
  );

  drawLabel(
    ctx,
    rightLabel,
    rightAnchor.x,
    rightLabelY,
    216
  );

  // Main caption stays below the cutouts.
  drawCaption(
    ctx,
    caption,
    captionTop
  );

  return canvas.toDataURL("image/png");
}
