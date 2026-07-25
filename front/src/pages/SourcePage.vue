<template>
  <div class="source-page">
    <!-- 顶部 -->
    <header class="topbar">
      <button class="back-btn" @click="goTo('feed')" aria-label="返回">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#2d4a3e" stroke-width="2.2" stroke-linecap="round">
          <path d="M15 5l-7 7 7 7" />
        </svg>
      </button>
      <button class="capsule-close light" @click="goTo('feed')" aria-label="退出">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#2d4a3e" stroke-width="2.2" stroke-linecap="round">
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>
    </header>

    <div class="scroll-body">
      <!-- 品牌区：鲜艳鲜花图标 + 万物生花 -->
      <div class="brand fade-up">
        <span class="brand-icon">
          <img src="/icon.png" class="brand-icon-img" alt="万物生花" />
        </span>
        <h1 class="brand-name">万物生花</h1>
      </div>

      <p class="slogan fade-up" style="animation-delay:.08s">把任何画面，变成一束花</p>

      <!-- 画面预览区：默认展示视频暂停帧，拍摄/相册选择后覆盖 -->
      <div class="preview-wrap fade-up" style="animation-delay:.16s">
        <div class="preview-frame">
          <img v-if="displayImage" :src="displayImage" class="preview-img" alt="画面来源" />
          <div v-else class="preview-placeholder">
            <svg viewBox="0 0 24 24" width="42" height="42" fill="none" stroke="rgba(255,255,255,.7)" stroke-width="1.5">
              <rect x="3" y="6" width="18" height="14" rx="3" />
              <circle cx="12" cy="13" r="3.5" />
              <path d="M9 6l1.2-2h3.6L15 6" />
            </svg>
            <p>拍摄或选择一个画面</p>
          </div>
          <span v-if="imageFrom === 'snapshot'" class="preview-badge">来自刚才的视频</span>
          <span v-else-if="imageFrom === 'pick'" class="preview-badge picked">已替换</span>
        </div>
      </div>

      <!-- 提交 -->
      <div class="submit-wrap fade-up" style="animation-delay:.24s">
        <button class="primary-btn" :disabled="!displayImage || submitting" @click="submit">
          {{ submitting ? '' : '提交，生成我的花束' }}
          <span v-if="submitting" class="btn-loading"><span class="spinner"></span></span>
        </button>
        <p v-if="submitting" class="submitting-hint">AI 正在识别画面：人物 · 地点 · 色调 · 情绪…</p>
      </div>
    </div>

    <!-- 底部：选择画面来源 + 居中相机按钮 -->
    <footer class="bottom-bar">
      <p class="source-label">选择画面来源</p>
      <button class="camera-btn" @click="sheetVisible = true" aria-label="拍摄或从相册选择">
        <svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="#fff" stroke-width="1.8">
          <rect x="2.5" y="6.5" width="19" height="13" rx="3.5" />
          <circle cx="12" cy="13" r="4" />
          <path d="M8.5 6.5L10 4h4l1.5 2.5" />
          <circle cx="18" cy="10" r="0.6" fill="#fff" />
        </svg>
      </button>
    </footer>

    <!-- 拍摄 / 相册 选择面板 -->
    <transition name="sheet">
      <div v-if="sheetVisible" class="sheet-mask" @click="sheetVisible = false">
        <div class="sheet" @click.stop>
          <button class="sheet-item" @click="pick('camera')">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#1a1a1a" stroke-width="1.8">
              <rect x="2.5" y="6.5" width="19" height="13" rx="3.5" />
              <circle cx="12" cy="13" r="4" />
              <path d="M8.5 6.5L10 4h4l1.5 2.5" />
            </svg>
            拍摄眼前画面
          </button>
          <button class="sheet-item" @click="pick('album')">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#1a1a1a" stroke-width="1.8">
              <rect x="3" y="4" width="18" height="16" rx="3" />
              <circle cx="9" cy="10" r="1.8" />
              <path d="M4 18l5-5 3.5 3.5L16 13l4 4" />
            </svg>
            从相册选择
          </button>
          <button class="sheet-cancel" @click="sheetVisible = false">取消</button>
        </div>
      </div>
    </transition>

    <input ref="cameraInput" type="file" accept="image/*" capture="environment" hidden @change="onFile" />
    <input ref="albumInput" type="file" accept="image/*" hidden @change="onFile" />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { store, goTo } from '../store'
import { analyzeImage } from '../api'

const sheetVisible = ref(false)
const submitting = ref(false)
const cameraInput = ref(null)
const albumInput = ref(null)
const pickedImage = ref('')
const pickedFileName = ref('')

const displayImage = computed(() => pickedImage.value || store.videoSnapshot || '')
const imageFrom = computed(() => (pickedImage.value ? 'pick' : store.videoSnapshot ? 'snapshot' : ''))

function pick(type) {
  sheetVisible.value = false
  const input = type === 'camera' ? cameraInput.value : albumInput.value
  input.value = ''
  input.click()
}

function onFile(e) {
  const file = e.target.files[0]
  if (!file) return
  pickedFileName.value = file.name || ''
  const reader = new FileReader()
  reader.onload = () => {
    pickedImage.value = reader.result
  }
  reader.readAsDataURL(file)
}

async function submit() {
  if (!displayImage.value || submitting.value) return
  submitting.value = true
  store.sourceImage = displayImage.value
  try {
    store.sourceMeta = {
      fileName: pickedFileName.value || 'snapshot.jpg'
    }
    store.analysis = await analyzeImage({
      imageDataUrl: displayImage.value,
      fileName: store.sourceMeta.fileName,
      voiceText: store.voiceText
    })
    store.selectedInterpretationId = store.analysis.recommended_interpretation_id || ''
    store.references = []
    store.bouquet = null
    store.selectedBouquetIndex = 0
    store.editedBouquetImage = ''
    store.emotion = null
    goTo('analysis')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.source-page {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(120% 60% at 50% -10%, #e8dcc8 0%, transparent 65%),
    linear-gradient(180deg, #f5f1e8 0%, #efe9dc 55%, #e9e2d2 100%);
  display: flex;
  flex-direction: column;
  color: var(--ink);
  overflow: hidden;
}

.topbar {
  position: relative;
  height: calc(var(--safe-top) + 52px);
  flex-shrink: 0;
}
.back-btn {
  position: absolute;
  top: calc(var(--safe-top) + 12px);
  left: 12px;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: rgba(45, 74, 62, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
}

.scroll-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 24px 12px;
  display: flex;
  flex-direction: column;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 6px;
}
.brand-icon {
  width: 62px;
  height: 62px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.brand-icon-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  /* 白色花纹 -> 墨绿 */
  filter: brightness(0) saturate(100%) invert(27%) sepia(12%) saturate(1400%) hue-rotate(95deg) brightness(0.9) contrast(1.05);
}
.brand-name {
  font-size: 30px;
  font-weight: 800;
  letter-spacing: 4px;
  background: linear-gradient(120deg, #2d4a3e, #3d6b57 55%, #d4859a);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.slogan {
  margin-top: 14px;
  font-size: 17px;
  color: rgba(34, 48, 42, 0.7);
  letter-spacing: 1.5px;
}

.preview-wrap {
  margin-top: 22px;
  flex: 1;
  min-height: 0;
  display: flex;
}
.preview-frame {
  position: relative;
  width: 100%;
  border-radius: 22px;
  overflow: hidden;
  background: #fff;
  border: 1px solid rgba(45, 74, 62, 0.1);
  box-shadow: 0 10px 28px rgba(45, 74, 62, 0.1);
  min-height: 260px;
}
.preview-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  position: absolute;
  inset: 0;
}
.preview-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: rgba(34, 48, 42, 0.45);
  font-size: 14px;
  letter-spacing: 1px;
}
.preview-badge {
  position: absolute;
  left: 12px;
  top: 12px;
  padding: 5px 12px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(6px);
  font-size: 12px;
  color: rgba(255, 255, 255, 0.9);
}
.preview-badge.picked {
  background: rgba(61, 107, 87, 0.85);
}

.submit-wrap {
  margin-top: 20px;
}
.btn-loading {
  display: inline-flex;
  justify-content: center;
}
.btn-loading .spinner {
  width: 22px;
  height: 22px;
  border-width: 2.5px;
}
.submitting-hint {
  margin-top: 12px;
  text-align: center;
  font-size: 12.5px;
  color: rgba(34, 48, 42, 0.5);
  letter-spacing: 1px;
}

/* 底部相机 */
.bottom-bar {
  flex-shrink: 0;
  padding: 10px 0 calc(var(--safe-bottom) + 18px);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}
.source-label {
  font-size: 12.5px;
  color: rgba(34, 48, 42, 0.5);
  letter-spacing: 2px;
}
.camera-btn {
  width: 68px;
  height: 68px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--brand) 0%, var(--brand-deep) 100%);
  border: 3px solid #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 10px 26px rgba(45, 74, 62, 0.3);
}
.camera-btn:active {
  transform: scale(0.93);
}

/* 底部弹层 */
.sheet-mask {
  position: absolute;
  inset: 0;
  z-index: 60;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: flex-end;
}
.sheet {
  width: 100%;
  background: #fff;
  border-radius: 20px 20px 0 0;
  padding: 10px 16px calc(var(--safe-bottom) + 14px);
}
.sheet-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 16px 0;
  font-size: 16px;
  color: #1a1a1a;
  border-bottom: 1px solid #f0ebe6;
}
.sheet-cancel {
  width: 100%;
  padding: 15px 0;
  margin-top: 8px;
  font-size: 15px;
  color: #999;
}
.sheet-enter-active,
.sheet-leave-active {
  transition: opacity 0.25s ease;
}
.sheet-enter-active .sheet {
  transition: transform 0.3s cubic-bezier(0.32, 0.72, 0.24, 1);
}
.sheet-enter-from,
.sheet-leave-to {
  opacity: 0;
}
.sheet-enter-from .sheet {
  transform: translateY(100%);
}
</style>
