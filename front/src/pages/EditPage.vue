<template>
  <div class="edit-page">
    <header class="topbar">
      <button class="back-btn" @click="goTo('bouquet')" aria-label="返回">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#1a1a1a" stroke-width="2.2" stroke-linecap="round">
          <path d="M15 5l-7 7 7 7" />
        </svg>
      </button>
      <span class="topbar-title">局部共创编辑</span>
      <button class="capsule-close light" @click="goTo('feed')" aria-label="退出">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#1a1a1a" stroke-width="2.2" stroke-linecap="round">
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>
    </header>

    <div class="scroll-body">
      <section class="canvas-card">
        <div class="tool-row">
          <button class="tool-btn" :class="{ active: tool === 'brush' }" @click="setTool('brush')">涂抹</button>
          <button class="tool-btn" :class="{ active: tool === 'box' }" @click="setTool('box')">框选</button>
          <label class="brush-size">
            笔刷
            <input v-model="brushSize" type="range" min="12" max="64" />
          </label>
        </div>

        <div class="canvas-wrap">
          <canvas
            ref="canvasRef"
            class="edit-canvas"
            @pointerdown="onPointerDown"
            @pointermove="onPointerMove"
            @pointerup="finishDrawing"
            @pointercancel="finishDrawing"
            @pointerleave="onPointerLeave"
          ></canvas>
        </div>

        <div class="tool-row secondary">
          <button class="text-btn" @click="undoSelection">撤销</button>
          <button class="text-btn" @click="clearSelections">清空</button>
          <span class="selection-count">{{ selections.length }} 个区域</span>
        </div>
      </section>

      <section class="panel-card">
        <p class="panel-title">修改指令</p>
        <textarea
          v-model.trim="prompt"
          class="prompt-input"
          placeholder="例如：把涂抹区域改成更克制的白绿色花材，保持背景和包装不变。"
        ></textarea>
        <p class="status" :class="{ error: !!errorText }">{{ errorText || statusText }}</p>
        <div class="action-row">
          <button class="ghost-btn" @click="previewResult" :disabled="!resultImageUrl">预览结果</button>
          <button class="primary-btn" @click="submitEdit" :disabled="submitting">
            {{ submitting ? '生成中...' : '生成修改图' }}
          </button>
        </div>
      </section>

      <section v-if="resultImageUrl" class="result-card">
        <p class="panel-title">修改结果</p>
        <img :src="resultImageUrl" class="result-image" alt="编辑结果" />
        <div class="action-row">
          <button class="ghost-btn" @click="resetResult">重做</button>
          <button class="primary-btn" @click="applyResult">应用到花束</button>
        </div>
      </section>
    </div>

    <!-- 生成进度遮罩 -->
    <div v-if="submitting" class="generating-cover">
      <div class="generating-card">
        <span class="gen-spinner"></span>
        <p class="gen-title">正在生成修改图</p>
        <div class="gen-track">
          <div class="gen-fill" :style="{ width: genProgress + '%' }"></div>
        </div>
        <p class="gen-num">{{ genProgress }}%</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { editImage } from '../api'
import { goTo, store } from '../store'

const canvasRef = ref(null)
const brushSize = ref(28)
const tool = ref('brush')
const prompt = ref('')
const statusText = ref('先在花束图上涂抹或框选，再输入修改指令。')
const errorText = ref('')
const submitting = ref(false)
const resultImageUrl = ref('')
const genProgress = ref(0)
let genTimer = null
const imageEl = ref(null)
const drawing = ref(false)
const activeStroke = ref(null)
const activeBox = ref(null)
const selections = ref([])

const currentResult = computed(
  () => store.bouquet?.results?.[store.selectedBouquetIndex] || null
)
const sourceImageUrl = computed(() => store.editedBouquetImage || currentResult.value?.bouquet_image || '')

watch(sourceImageUrl, async () => {
  await loadImage()
})

onMounted(loadImage)

function setTool(nextTool) {
  tool.value = nextTool
}

/* 将跨域图片 fetch 为本地 objectURL，避免 canvas 被污染（tainted）导致无法 toDataURL */
async function toLocalImageUrl(src) {
  if (!src) return src
  // dataURL / blob 本身就是同源，直接返回
  if (src.startsWith('data:') || src.startsWith('blob:')) return src
  try {
    const resp = await fetch(src, { mode: 'cors' })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const blob = await resp.blob()
    return URL.createObjectURL(blob)
  } catch {
    // fetch 失败则退回原地址（依赖 crossOrigin + 服务器 CORS 头）
    return src
  }
}

async function loadImage() {
  if (!sourceImageUrl.value || !canvasRef.value) return

  const localUrl = await toLocalImageUrl(sourceImageUrl.value)
  const image = await new Promise((resolve, reject) => {
    const el = new Image()
    el.crossOrigin = 'anonymous'
    el.onload = () => resolve(el)
    el.onerror = () => reject(new Error('花束图加载失败。'))
    el.src = localUrl
  }).catch((error) => {
    errorText.value = error.message
    return null
  })

  if (!image) return
  imageEl.value = image
  selections.value = []
  activeStroke.value = null
  activeBox.value = null
  errorText.value = ''
  statusText.value = '先在花束图上涂抹或框选，再输入修改指令。'
  resultImageUrl.value = ''

  await nextTick()
  const canvas = canvasRef.value
  canvas.width = image.naturalWidth
  canvas.height = image.naturalHeight
  renderCanvas()
}

function getCanvasPoint(event) {
  const canvas = canvasRef.value
  const rect = canvas.getBoundingClientRect()
  const x = ((event.clientX - rect.left) / rect.width) * canvas.width
  const y = ((event.clientY - rect.top) / rect.height) * canvas.height
  return {
    x: Math.max(0, Math.min(canvas.width, x)),
    y: Math.max(0, Math.min(canvas.height, y))
  }
}

function getBrushSizeInImagePixels() {
  const canvas = canvasRef.value
  const rect = canvas.getBoundingClientRect()
  const scale = rect.width > 0 ? canvas.width / rect.width : 1
  return Number(brushSize.value) * scale
}

function normalizeBox(box) {
  const canvas = canvasRef.value
  const left = Math.max(0, Math.min(box.x1, box.x2))
  const top = Math.max(0, Math.min(box.y1, box.y2))
  const right = Math.min(canvas.width, Math.max(box.x1, box.x2))
  const bottom = Math.min(canvas.height, Math.max(box.y1, box.y2))
  return [Math.round(left), Math.round(top), Math.round(right), Math.round(bottom)]
}

function boxFromStroke(points, size) {
  const pad = size / 2
  const xs = points.map((point) => point.x)
  const ys = points.map((point) => point.y)
  return normalizeBox({
    x1: Math.min(...xs) - pad,
    y1: Math.min(...ys) - pad,
    x2: Math.max(...xs) + pad,
    y2: Math.max(...ys) + pad
  })
}

function drawStroke(ctx, points, size) {
  if (!points.length) return
  ctx.save()
  ctx.strokeStyle = 'rgba(28, 126, 214, 0.42)'
  ctx.lineWidth = size
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.beginPath()
  ctx.moveTo(points[0].x, points[0].y)
  points.slice(1).forEach((point) => ctx.lineTo(point.x, point.y))
  if (points.length === 1) {
    ctx.lineTo(points[0].x + 0.1, points[0].y + 0.1)
  }
  ctx.stroke()
  ctx.restore()
}

function drawBox(ctx, box) {
  const [left, top, right, bottom] = box
  ctx.save()
  ctx.fillStyle = 'rgba(28, 126, 214, 0.2)'
  ctx.strokeStyle = 'rgba(21, 95, 167, 0.9)'
  ctx.lineWidth = Math.max(2, canvasRef.value.width / 600)
  ctx.fillRect(left, top, right - left, bottom - top)
  ctx.strokeRect(left, top, right - left, bottom - top)
  ctx.restore()
}

function renderCanvas() {
  const canvas = canvasRef.value
  const ctx = canvas?.getContext('2d')
  if (!canvas || !ctx || !imageEl.value) return

  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.drawImage(imageEl.value, 0, 0, canvas.width, canvas.height)

  selections.value.forEach((selection) => {
    if (selection.type === 'brush') {
      drawStroke(ctx, selection.points, selection.size)
    }
    drawBox(ctx, selection.box)
  })

  if (activeStroke.value) {
    drawStroke(ctx, activeStroke.value.points, activeStroke.value.size)
    drawBox(ctx, boxFromStroke(activeStroke.value.points, activeStroke.value.size))
  }
  if (activeBox.value) {
    drawBox(ctx, normalizeBox(activeBox.value))
  }
}

function onPointerDown(event) {
  if (!imageEl.value) return
  event.preventDefault()
  canvasRef.value.setPointerCapture(event.pointerId)
  const point = getCanvasPoint(event)
  drawing.value = true
  errorText.value = ''

  if (tool.value === 'brush') {
    activeStroke.value = {
      points: [point],
      size: getBrushSizeInImagePixels()
    }
  } else {
    activeBox.value = { x1: point.x, y1: point.y, x2: point.x, y2: point.y }
  }
  renderCanvas()
}

function onPointerMove(event) {
  if (!drawing.value) return
  event.preventDefault()
  const point = getCanvasPoint(event)
  if (activeStroke.value) {
    activeStroke.value.points.push(point)
  }
  if (activeBox.value) {
    activeBox.value.x2 = point.x
    activeBox.value.y2 = point.y
  }
  renderCanvas()
}

function finishDrawing() {
  if (!drawing.value) return
  drawing.value = false

  if (activeStroke.value) {
    const points = activeStroke.value.points
    const size = activeStroke.value.size
    if (points.length) {
      selections.value.push({
        type: 'brush',
        points,
        size,
        box: boxFromStroke(points, size)
      })
    }
    activeStroke.value = null
  }

  if (activeBox.value) {
    const box = normalizeBox(activeBox.value)
    if (box[2] - box[0] >= 4 && box[3] - box[1] >= 4) {
      selections.value.push({ type: 'box', box })
    }
    activeBox.value = null
  }

  if (selections.value.length > 2) {
    selections.value = selections.value.slice(-2)
    statusText.value = '当前模型单张图最多支持 2 个区域，已保留最近 2 个。'
  } else {
    statusText.value = '区域已记录，可以继续补充指令。'
  }
  renderCanvas()
}

function onPointerLeave() {
  if (drawing.value) finishDrawing()
}

function undoSelection() {
  selections.value.pop()
  renderCanvas()
}

function clearSelections() {
  selections.value = []
  activeStroke.value = null
  activeBox.value = null
  renderCanvas()
}

function exportOriginalAsJpeg() {
  const output = document.createElement('canvas')
  output.width = canvasRef.value.width
  output.height = canvasRef.value.height
  const ctx = output.getContext('2d')
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, output.width, output.height)
  ctx.drawImage(imageEl.value, 0, 0, output.width, output.height)
  return output.toDataURL('image/jpeg', 0.92)
}

async function submitEdit() {
  if (!imageEl.value) {
    errorText.value = '花束图还没准备好。'
    return
  }
  if (!prompt.value) {
    errorText.value = '请输入修改指令。'
    return
  }
  if (!selections.value.length) {
    errorText.value = '请先涂抹或框选需要修改的位置。'
    return
  }

  submitting.value = true
  errorText.value = ''
  statusText.value = '正在提交给模型，请稍等。'
  genProgress.value = 0
  clearInterval(genTimer)
  genTimer = setInterval(() => {
    // 进度到 92% 后放缓，等待真实结果
    const step = genProgress.value < 70 ? Math.random() * 9 + 5 : Math.random() * 3 + 1
    genProgress.value = Math.min(genProgress.value + step, 92)
  }, 200)

  try {
    const result = await editImage({
      imageDataUrl: exportOriginalAsJpeg(),
      prompt: prompt.value,
      boxes: selections.value.map((selection) => selection.box)
    })
    genProgress.value = 100
    resultImageUrl.value = result.imageUrl
    statusText.value = result.requestId ? `生成完成 · ${result.requestId}` : '生成完成。'
    // 生成成功后应用并进入花束页
    store.editedBouquetImage = result.imageUrl
    setTimeout(() => {
      submitting.value = false
      goTo('bouquet')
    }, 450)
  } catch (error) {
    errorText.value = error.message || '生成失败。'
    submitting.value = false
  } finally {
    clearInterval(genTimer)
    genTimer = null
  }
}

function previewResult() {
  if (resultImageUrl.value) {
    window.open(resultImageUrl.value, '_blank')
  }
}

function resetResult() {
  resultImageUrl.value = ''
  statusText.value = '已清空结果，可以重新圈选并再试一版。'
}

function applyResult() {
  if (!resultImageUrl.value) return
  store.editedBouquetImage = resultImageUrl.value
  goTo('bouquet')
}
</script>

<style scoped>
.edit-page {
  position: absolute;
  inset: 0;
  background: var(--paper);
  display: flex;
  flex-direction: column;
}

.topbar {
  position: relative;
  height: calc(var(--safe-top) + 52px);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-top: var(--safe-top);
}

.topbar-title {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 2px;
}

.back-btn {
  position: absolute;
  left: 12px;
  top: calc(var(--safe-top) + 9px);
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.05);
  display: flex;
  align-items: center;
  justify-content: center;
}

.scroll-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 18px calc(var(--safe-bottom) + 24px);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.canvas-card,
.panel-card,
.result-card {
  background: #fff;
  border-radius: 22px;
  padding: 16px;
  box-shadow: 0 10px 26px rgba(90, 60, 40, 0.08);
}

.tool-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.tool-row.secondary {
  justify-content: space-between;
  margin-top: 12px;
}

.tool-btn,
.text-btn,
.ghost-btn {
  border-radius: 999px;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
}

.tool-btn {
  background: #f3eee8;
  color: #7a6a5c;
}

.tool-btn.active {
  background: rgba(61, 107, 87, 0.12);
  color: var(--brand-deep);
}

.text-btn,
.ghost-btn {
  border: 1px solid #ddd0c0;
  color: #7a6a5c;
}

.brush-size {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #8c7b6d;
}

.canvas-wrap {
  margin-top: 14px;
  border-radius: 18px;
  overflow: hidden;
  background: #efe9e1;
}

.edit-canvas {
  display: block;
  width: 100%;
  height: auto;
  max-height: 56vh;
  touch-action: none;
}

.selection-count,
.status {
  font-size: 12.5px;
  color: #8c7b6d;
  line-height: 1.6;
}

.status.error {
  color: #b83b5e;
}

.panel-title {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 1px;
  color: #5f4c3f;
}

.prompt-input {
  width: 100%;
  min-height: 120px;
  margin-top: 12px;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid #e5dbcf;
  background: #faf6f0;
  resize: vertical;
  font: inherit;
  color: var(--ink);
}

.action-row {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}

.action-row .ghost-btn {
  flex: 1;
}

.action-row .primary-btn {
  flex: 1.3;
}

.result-image {
  width: 100%;
  margin-top: 12px;
  border-radius: 16px;
  object-fit: cover;
}

/* 生成进度遮罩 */
.generating-cover {
  position: absolute;
  inset: 0;
  z-index: 90;
  background: rgba(250, 246, 241, 0.96);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 30px;
}
.generating-card {
  width: 100%;
  max-width: 300px;
  text-align: center;
}
.gen-spinner {
  display: inline-block;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 3.5px solid rgba(61, 107, 87, 0.18);
  border-top-color: var(--brand-deep);
  animation: gen-spin 0.9s linear infinite;
  margin-bottom: 20px;
}
@keyframes gen-spin {
  to {
    transform: rotate(360deg);
  }
}
.gen-title {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #3a2f28;
}
.gen-track {
  margin-top: 22px;
  height: 8px;
  border-radius: 999px;
  background: #f0e8de;
  overflow: hidden;
}
.gen-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #6a9a82, #3d6b57);
  transition: width 0.2s ease;
}
.gen-num {
  margin-top: 12px;
  font-size: 13px;
  color: #9a8a7c;
  font-family: ui-monospace, monospace;
}
</style>
