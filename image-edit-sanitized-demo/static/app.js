const canvas = document.querySelector("#editCanvas");
const ctx = canvas.getContext("2d");
const imageInput = document.querySelector("#imageInput");
const imageMeta = document.querySelector("#imageMeta");
const emptyState = document.querySelector("#emptyState");
const brushTool = document.querySelector("#brushTool");
const boxTool = document.querySelector("#boxTool");
const brushSizeInput = document.querySelector("#brushSize");
const undoButton = document.querySelector("#undoButton");
const clearButton = document.querySelector("#clearButton");
const selectionCount = document.querySelector("#selectionCount");
const promptInput = document.querySelector("#promptInput");
const generateButton = document.querySelector("#generateButton");
const statusText = document.querySelector("#statusText");
const resultImage = document.querySelector("#resultImage");

const state = {
  tool: "brush",
  image: null,
  imageDataUrl: "",
  selections: [],
  drawing: false,
  activeStroke: null,
  activeBox: null,
};

function setStatus(message, isError = false) {
  statusText.textContent = message;
  statusText.classList.toggle("error", isError);
}

function setTool(tool) {
  state.tool = tool;
  brushTool.classList.toggle("active", tool === "brush");
  boxTool.classList.toggle("active", tool === "box");
}

function updateSelectionCount() {
  selectionCount.textContent = `${state.selections.length} 个区域`;
}

function getCanvasPoint(event) {
  const rect = canvas.getBoundingClientRect();
  const x = ((event.clientX - rect.left) / rect.width) * canvas.width;
  const y = ((event.clientY - rect.top) / rect.height) * canvas.height;
  return {
    x: Math.max(0, Math.min(canvas.width, x)),
    y: Math.max(0, Math.min(canvas.height, y)),
  };
}

function getBrushSizeInImagePixels() {
  const rect = canvas.getBoundingClientRect();
  const scale = rect.width > 0 ? canvas.width / rect.width : 1;
  return Number(brushSizeInput.value) * scale;
}

function normalizeBox(box) {
  const left = Math.max(0, Math.min(box.x1, box.x2));
  const top = Math.max(0, Math.min(box.y1, box.y2));
  const right = Math.min(canvas.width, Math.max(box.x1, box.x2));
  const bottom = Math.min(canvas.height, Math.max(box.y1, box.y2));
  return [Math.round(left), Math.round(top), Math.round(right), Math.round(bottom)];
}

function boxFromStroke(points, size) {
  const pad = size / 2;
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  return normalizeBox({
    x1: Math.min(...xs) - pad,
    y1: Math.min(...ys) - pad,
    x2: Math.max(...xs) + pad,
    y2: Math.max(...ys) + pad,
  });
}

function drawStroke(points, size) {
  if (points.length === 0) return;
  ctx.save();
  ctx.strokeStyle = "rgba(28, 126, 214, 0.42)";
  ctx.lineWidth = size;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  points.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
  if (points.length === 1) {
    ctx.lineTo(points[0].x + 0.1, points[0].y + 0.1);
  }
  ctx.stroke();
  ctx.restore();
}

function drawBox(box) {
  const [left, top, right, bottom] = box;
  const width = right - left;
  const height = bottom - top;
  ctx.save();
  ctx.fillStyle = "rgba(28, 126, 214, 0.2)";
  ctx.strokeStyle = "rgba(21, 95, 167, 0.9)";
  ctx.lineWidth = Math.max(2, canvas.width / 600);
  ctx.fillRect(left, top, width, height);
  ctx.strokeRect(left, top, width, height);
  ctx.restore();
}

function renderCanvas() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!state.image) return;

  ctx.drawImage(state.image, 0, 0, canvas.width, canvas.height);
  state.selections.forEach((selection) => {
    if (selection.type === "brush") {
      drawStroke(selection.points, selection.size);
      drawBox(selection.box);
    } else {
      drawBox(selection.box);
    }
  });

  if (state.activeStroke) {
    drawStroke(state.activeStroke.points, state.activeStroke.size);
    drawBox(boxFromStroke(state.activeStroke.points, state.activeStroke.size));
  }
  if (state.activeBox) {
    drawBox(normalizeBox(state.activeBox));
  }
}

function exportOriginalAsJpeg() {
  const output = document.createElement("canvas");
  output.width = canvas.width;
  output.height = canvas.height;
  const outputCtx = output.getContext("2d");
  outputCtx.fillStyle = "#ffffff";
  outputCtx.fillRect(0, 0, output.width, output.height);
  outputCtx.drawImage(state.image, 0, 0, output.width, output.height);
  return output.toDataURL("image/jpeg", 0.92);
}

function loadImage(file) {
  const reader = new FileReader();
  reader.onload = () => {
    const image = new Image();
    image.onload = () => {
      state.image = image;
      state.imageDataUrl = reader.result;
      state.selections = [];
      state.activeStroke = null;
      state.activeBox = null;

      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      canvas.style.display = "block";
      emptyState.style.display = "none";
      imageMeta.textContent = `${file.name} · ${image.naturalWidth} × ${image.naturalHeight}`;
      resultImage.style.display = "none";
      resultImage.removeAttribute("src");
      setStatus("");
      updateSelectionCount();
      renderCanvas();
    };
    image.onerror = () => setStatus("图片读取失败，请换一张图片。", true);
    image.src = reader.result;
  };
  reader.onerror = () => setStatus("文件读取失败。", true);
  reader.readAsDataURL(file);
}

function finishDrawing() {
  if (!state.drawing) return;
  state.drawing = false;

  if (state.activeStroke) {
    const points = state.activeStroke.points;
    const size = state.activeStroke.size;
    if (points.length > 0) {
      state.selections.push({
        type: "brush",
        points,
        size,
        box: boxFromStroke(points, size),
      });
    }
    state.activeStroke = null;
  }

  if (state.activeBox) {
    const box = normalizeBox(state.activeBox);
    if (box[2] - box[0] >= 4 && box[3] - box[1] >= 4) {
      state.selections.push({ type: "box", box });
    }
    state.activeBox = null;
  }

  if (state.selections.length > 2) {
    state.selections = state.selections.slice(-2);
    setStatus("当前模型单张图最多支持 2 个区域，已保留最近 2 个。");
  } else {
    setStatus("");
  }

  updateSelectionCount();
  renderCanvas();
}

imageInput.addEventListener("change", (event) => {
  const [file] = event.target.files;
  if (file) loadImage(file);
});

brushTool.addEventListener("click", () => setTool("brush"));
boxTool.addEventListener("click", () => setTool("box"));

undoButton.addEventListener("click", () => {
  state.selections.pop();
  updateSelectionCount();
  renderCanvas();
});

clearButton.addEventListener("click", () => {
  state.selections = [];
  state.activeStroke = null;
  state.activeBox = null;
  setStatus("");
  updateSelectionCount();
  renderCanvas();
});

canvas.addEventListener("pointerdown", (event) => {
  if (!state.image) return;
  event.preventDefault();
  canvas.setPointerCapture(event.pointerId);
  const point = getCanvasPoint(event);
  state.drawing = true;

  if (state.tool === "brush") {
    state.activeStroke = {
      points: [point],
      size: getBrushSizeInImagePixels(),
    };
  } else {
    state.activeBox = {
      x1: point.x,
      y1: point.y,
      x2: point.x,
      y2: point.y,
    };
  }
  renderCanvas();
});

canvas.addEventListener("pointermove", (event) => {
  if (!state.drawing) return;
  event.preventDefault();
  const point = getCanvasPoint(event);

  if (state.activeStroke) {
    state.activeStroke.points.push(point);
  }
  if (state.activeBox) {
    state.activeBox.x2 = point.x;
    state.activeBox.y2 = point.y;
  }
  renderCanvas();
});

canvas.addEventListener("pointerup", finishDrawing);
canvas.addEventListener("pointercancel", finishDrawing);
canvas.addEventListener("pointerleave", () => {
  if (state.drawing) finishDrawing();
});

generateButton.addEventListener("click", async () => {
  if (!state.image) {
    setStatus("请先上传图片。", true);
    return;
  }

  const prompt = promptInput.value.trim();
  if (!prompt) {
    setStatus("请输入修改指令。", true);
    promptInput.focus();
    return;
  }

  const boxes = state.selections.map((selection) => selection.box);
  if (boxes.length === 0) {
    setStatus("请先涂抹或框选需要修改的位置。", true);
    return;
  }

  generateButton.disabled = true;
  generateButton.textContent = "生成中...";
  setStatus("正在提交给模型，请稍等。");

  try {
    const response = await fetch("/api/image/edit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        imageDataUrl: exportOriginalAsJpeg(),
        prompt,
        boxes,
      }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "生成失败。");
    }

    resultImage.src = data.imageUrl;
    resultImage.style.display = "block";
    setStatus(data.requestId ? `生成完成 · ${data.requestId}` : "生成完成。");
  } catch (error) {
    setStatus(error.message || "生成失败。", true);
  } finally {
    generateButton.disabled = false;
    generateButton.textContent = "生成修改图";
  }
});

setTool("brush");
updateSelectionCount();
