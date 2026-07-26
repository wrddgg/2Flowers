<template>
  <div class="tutorial-page">
    <!-- ===== 阶段1：加载中（白卡覆盖全屏，循环切换花+花语） ===== -->
    <div v-if="phase === 'loading'" class="loading-cover">
      <div class="loading-card">
        <div class="loading-spinner-wrap">
          <span class="spinner dark"></span>
        </div>
        <p class="loading-title">正在生成制作教程</p>
        <transition name="flower-fade" mode="out-in">
          <div class="loading-flower" :key="rotating.name" v-if="rotating">
            <span class="lf-dot" :class="{ foliage: rotating.category === 'foliage' }"></span>
            <p class="lf-name">{{ rotating.name }}</p>
            <p class="lf-meaning">{{ rotating.meaning }}</p>
          </div>
        </transition>
      </div>
    </div>

    <!-- ===== 阶段2：教程步骤 ===== -->
    <template v-else-if="phase === 'steps'">
      <header class="topbar">
        <button class="back-btn" @click="goTo('card')" aria-label="返回">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#1a1a1a" stroke-width="2.2" stroke-linecap="round">
            <path d="M15 5l-7 7 7 7" />
          </svg>
        </button>
        <span class="topbar-title">制作教程</span>
        <button class="capsule-close light" @click="exitToFeed" aria-label="退出">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#1a1a1a" stroke-width="2.2" stroke-linecap="round">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </header>

      <div class="scroll-body">
        <!-- 步骤进度 -->
        <div class="step-progress">
          <span
            v-for="(s, i) in steps"
            :key="i"
            class="sp-seg"
            :class="{ done: i < stepIndex, active: i === stepIndex }"
          ></span>
        </div>

        <transition name="step-slide" mode="out-in">
          <div class="step-card" :key="stepIndex" v-if="current">
            <p class="step-count">STEP {{ current.step }} / {{ steps.length }}</p>
            <h3 class="step-title">{{ current.title }}</h3>

            <!-- 步骤示意图 -->
            <div class="step-illustration">
              <!-- 图片正在生成中 -->
              <div v-if="isImageGenerating(current)" class="step-illu-placeholder step-illu-loading" :style="{ background: illuBg(stepIndex) }">
                <span class="illu-spinner"></span>
                <p class="illu-prompt">示意图正在生成中…</p>
              </div>
              <!-- 图片已生成 -->
              <template v-else-if="current.image_url && !isMockImg(current.image_url)">
                <div v-show="!imgLoaded" class="step-illu-placeholder step-illu-loading" :style="{ background: illuBg(stepIndex) }">
                  <span class="illu-spinner"></span>
                  <p class="illu-prompt">示意图加载中…</p>
                </div>
                <img
                  v-show="imgLoaded"
                  :src="current.image_url"
                  alt=""
                  @load="imgLoaded = true"
                  @error="imgLoaded = true"
                />
              </template>
              <!-- 图片生成失败/无图：占位符 -->
              <div v-else class="step-illu-placeholder" :style="{ background: illuBg(stepIndex) }">
                <span class="illu-num">{{ current.step }}</span>
                <p class="illu-prompt">{{ current.image_prompt }}</p>
              </div>
            </div>

            <p class="step-desc">{{ current.description }}</p>

            <!-- 用到的花材 -->
            <div class="step-flowers" v-if="stepIndex === 0">
              <span v-for="f in flowerNames" :key="f" class="sf-chip">{{ f }}</span>
            </div>
          </div>
        </transition>

        <div class="step-actions">
          <button v-if="stepIndex > 0" class="ghost-dark" @click="stepIndex--">上一步</button>
          <button v-if="stepIndex < steps.length - 1" class="primary-btn flex-1" @click="stepIndex++">
            下一步
          </button>
          <!-- 最后一步：完成并拍摄作品（带摄影图标） -->
          <button v-else class="primary-btn flex-1 finish-btn" @click="shootWork">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#fff" stroke-width="1.8">
              <rect x="2.5" y="6.5" width="19" height="13" rx="3.5" />
              <circle cx="12" cy="13" r="4" />
              <path d="M8.5 6.5L10 4h4l1.5 2.5" />
            </svg>
            完成并拍摄作品
          </button>
        </div>
      </div>
    </template>

    <!-- ===== 阶段2.5：预览拍摄的照片，确认或重拍 ===== -->
    <div v-else-if="phase === 'preview'" class="preview-cover">
      <header class="topbar dark">
        <span class="preview-title">确认你的作品</span>
        <button class="capsule-close" @click="exitToFeed" aria-label="退出">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </header>
      <div class="preview-body">
        <img :src="previewPhoto" class="preview-img" alt="拍摄的作品" />
        <div class="preview-actions">
          <button class="ghost-btn" @click="retakePhoto">重拍</button>
          <button class="primary-btn" @click="confirmPhoto">确认使用</button>
        </div>
      </div>
    </div>

    <!-- ===== 阶段3：生成对比图（进度条） ===== -->
    <div v-else-if="phase === 'composing'" class="loading-cover">
      <div class="loading-card">
        <p class="loading-title">正在生成对比图</p>
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: progress + '%' }"></div>
        </div>
        <p class="progress-num">{{ progress }}%</p>
      </div>
    </div>

    <!-- ===== 阶段4：对比图 + BGM + 分享 ===== -->
    <template v-else-if="phase === 'share'">
      <header class="topbar dark">
        <button class="back-btn" @click="phase = 'steps'" aria-label="返回">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round">
            <path d="M15 5l-7 7 7 7" />
          </svg>
        </button>
        <button class="capsule-close" @click="exitToFeed" aria-label="退出">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </header>

      <div class="share-body">
        <div class="compare-wrap fade-up">
          <img v-if="compareImage" :src="compareImage" class="compare-img" alt="对比图" />
        </div>

        <!-- BGM 选择 -->
        <div class="bgm-section fade-up" style="animation-delay:.1s">
          <p class="bgm-title">选择背景音乐</p>
          <div class="bgm-list">
            <button
              v-for="bgm in bgmOptions"
              :key="bgm.id"
              class="bgm-item"
              :class="{ active: selectedBgm === bgm.id }"
              @click="selectedBgm = bgm.id"
            >
              <span class="bgm-note">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8">
                  <path d="M9 18V5l12-2v13" />
                  <circle cx="6" cy="18" r="3" />
                  <circle cx="18" cy="16" r="3" />
                </svg>
              </span>
              <span class="bgm-info">
                <span class="bgm-name">{{ bgm.name }}</span>
                <span class="bgm-artist">{{ bgm.artist }}</span>
              </span>
              <span v-if="selectedBgm === bgm.id" class="bgm-check">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#fff" stroke-width="2.4">
                  <path d="M5 13l4 4L19 7" />
                </svg>
              </span>
            </button>
          </div>
        </div>

        <div class="share-actions fade-up" style="animation-delay:.18s">
          <button class="ghost-btn" @click="saveImage">保存图片</button>
          <button class="primary-btn douyin-btn" @click="shareToDouyin">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="#fff">
              <path d="M16.5 3c.4 2.3 1.9 3.8 4.2 4v3.1c-1.6 0-3-.5-4.2-1.3v6.6c0 3.9-2.7 6.6-6.3 6.6-3.5 0-6.2-2.6-6.2-6.1 0-3.6 2.8-6.2 6.6-6.1.3 0 .7 0 1 .1v3.2c-.3-.1-.6-.2-1-.2-1.8 0-3.1 1.3-3.1 3 0 1.8 1.4 3 3.1 3 1.9 0 3.1-1.3 3.1-3.4V3h2.8z"/>
            </svg>
            发到抖音
          </button>
        </div>
      </div>
    </template>

    <input ref="workInput" type="file" accept="image/*" capture="environment" hidden @change="onWorkPhoto" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { store, goTo, exitToFeed } from '../store'
import { generateTutorial, generateShareCard, pollTutorialStatus } from '../api'
import { composeCompareImage } from '../utils/compose'

const phase = ref('loading') // loading | steps | preview | composing | share
const previewPhoto = ref('')
const steps = computed(() => store.tutorial?.steps || [])
const stepIndex = ref(0)
const current = computed(() => steps.value[stepIndex.value])
const imgLoaded = ref(false)

// 切换步骤或图片地址变化时，重置加载态
watch(
  () => [stepIndex.value, current.value?.image_url],
  () => {
    imgLoaded.value = false
  }
)

// 同步教程进度到 store（供持久化，页面重载后恢复）
watch([phase, stepIndex, compareImage], () => {
  store.tutorialPhase = phase.value
  store.tutorialStepIndex = stepIndex.value
  store.compareImage = compareImage.value
})

const workInput = ref(null)
const progress = ref(0)
const compareImage = ref('')
const bgmOptions = ref([])
const selectedBgm = ref('')

/* 加载阶段：循环切换花+花语 */
const currentResult = computed(() => store.bouquet?.results?.[store.selectedBouquetIndex] || null)
const flowers = computed(() => currentResult.value?.flowers || [])
const rotateIndex = ref(0)
const rotating = computed(() => flowers.value[rotateIndex.value % Math.max(flowers.value.length, 1)])
let rotateTimer = null
let tutorialPollTimer = null

// 花材清单：复刻流程用 remake plan 重新规划的花材（轻量/氛围版花种有变化），否则用原花束花材
const flowerNames = computed(() => {
  const planFlowers = store.remakePlan?.selected_flowers
  if (store.isRemakeCard && Array.isArray(planFlowers) && planFlowers.length) {
    return planFlowers
  }
  return flowers.value.map((f) => f.name)
})

function isMockImg(url) {
  return url.startsWith('/mock/')
}

// 图片是否正在生成中（无图且状态为 pending/processing）
function isImageGenerating(step) {
  if (!step) return false
  if (step.image_url && !isMockImg(step.image_url)) return false
  const status = (step.image_status || '').toLowerCase()
  return status === 'pending' || status === 'processing' || status === 'running' || status === ''
}

function illuBg(i) {
  const bgs = [
    'linear-gradient(135deg,#ffe0e6,#ffb3c2)',
    'linear-gradient(135deg,#fff3d6,#ffd98a)',
    'linear-gradient(135deg,#e2f0e5,#a8d5b5)',
    'linear-gradient(135deg,#e6e0f5,#c3b2e3)'
  ]
  return bgs[i % bgs.length]
}

async function loadTutorial() {
  rotateTimer = setInterval(() => {
    rotateIndex.value++
  }, 2000)
  try {
    const tutorial = await generateTutorial({
      bouquetImage: store.remakePreviewImage || store.editedBouquetImage || currentResult.value?.bouquet_image || '',
      flowers: flowerNames.value,
      withImages: true
    })
    store.tutorial = tutorial
    if (tutorial.task_id && tutorial.status === 'processing') {
      startTutorialPolling(tutorial.task_id)
    }
    phase.value = 'steps'
  } finally {
    clearInterval(rotateTimer)
    rotateTimer = null
  }
}

function startTutorialPolling(taskId) {
  clearInterval(tutorialPollTimer)
  tutorialPollTimer = setInterval(async () => {
    try {
      const latest = await pollTutorialStatus(taskId)
      store.tutorial = latest
      if (latest.status === 'done' || latest.status === 'error') {
        clearInterval(tutorialPollTimer)
        tutorialPollTimer = null
      }
    } catch (error) {
      clearInterval(tutorialPollTimer)
      tutorialPollTimer = null
      console.warn(error)
    }
  }, 2500)
}

function shootWork() {
  workInput.value.value = ''
  workInput.value.click()
}

async function onWorkPhoto(e) {
  const file = e.target.files[0]
  if (!file) return
  const dataUrl = await fileToDataUrl(file)
  // 先让用户预览照片，选择确认或重拍
  previewPhoto.value = dataUrl
  phase.value = 'preview'
}

// 确认照片，生成对比图
async function confirmPhoto() {
  const dataUrl = previewPhoto.value
  store.workPhoto = dataUrl

  // 进度条阶段
  phase.value = 'composing'
  progress.value = 0
  const timer = setInterval(() => {
    progress.value = Math.min(progress.value + Math.random() * 14 + 6, 96)
  }, 180)

  // 对比图：要做的花（AI花束图） vs 用户做的花
  const targetImage = store.remakePreviewImage || store.editedBouquetImage || currentResult.value?.bouquet_image || store.sourceImage

  try {
    const [card, composed] = await Promise.all([
      generateShareCard({ before: targetImage, after: dataUrl, title: store.analysis?.title || '' }),
      composeCompareImage(targetImage, dataUrl, store.analysis?.title || '')
    ])
    store.shareCard = card
    compareImage.value = card.card_image || composed
    bgmOptions.value = card.bgm_options || []
    selectedBgm.value = bgmOptions.value[0]?.id || ''
    progress.value = 100
    setTimeout(() => (phase.value = 'share'), 350)
  } finally {
    clearInterval(timer)
  }
}

// 重拍
function retakePhoto() {
  previewPhoto.value = ''
  phase.value = 'steps'
  // 重新调起摄像头
  setTimeout(() => shootWork(), 100)
}

function fileToDataUrl(file) {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.readAsDataURL(file)
  })
}

function saveImage() {
  if (!compareImage.value) return
  const a = document.createElement('a')
  a.href = compareImage.value
  a.download = '万物生花-对比图.jpg'
  a.click()
}

function shareToDouyin() {
  const bgm = bgmOptions.value.find((b) => b.id === selectedBgm.value)
  alert(
    `已生成分享内容（演示）\n文案：${store.shareCard?.share_text || ''}\nBGM：${bgm ? bgm.name + ' - ' + bgm.artist : '无'}\n\n真实环境将调起抖音分享 SDK`
  )
}

onMounted(() => {
  // 页面重载恢复：已有教程数据且有保存的阶段，直接恢复到对应阶段，不重新生成
  if (store.tutorial && store.tutorialPhase) {
    phase.value = store.tutorialPhase
    stepIndex.value = store.tutorialStepIndex || 0
    compareImage.value = store.compareImage || ''
    if (store.tutorialPhase === 'share' && store.shareCard) {
      bgmOptions.value = store.shareCard.bgm_options || []
      selectedBgm.value = bgmOptions.value[0]?.id || ''
    }
    // 教程图片还在生成中则继续轮询
    if (store.tutorial.task_id && store.tutorial.status === 'processing') {
      startTutorialPolling(store.tutorial.task_id)
    }
    return
  }
  loadTutorial()
})
onBeforeUnmount(() => {
  if (rotateTimer) clearInterval(rotateTimer)
  if (tutorialPollTimer) clearInterval(tutorialPollTimer)
})
</script>

<style scoped>
.tutorial-page {
  position: absolute;
  inset: 0;
  background: var(--paper);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* ===== 加载白卡 ===== */
.loading-cover {
  position: absolute;
  inset: 0;
  z-index: 80;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 30px;
}

/* 照片预览确认 */
.preview-cover {
  position: absolute;
  inset: 0;
  z-index: 80;
  background: #1a1512;
  display: flex;
  flex-direction: column;
}
.preview-title {
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  letter-spacing: 1px;
}
.preview-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px 20px calc(var(--safe-bottom) + 20px);
  gap: 18px;
  overflow: hidden;
}
.preview-img {
  flex: 1;
  width: 100%;
  min-height: 0;
  object-fit: contain;
  border-radius: 16px;
  background: #000;
}
.preview-actions {
  display: flex;
  gap: 12px;
}
.preview-actions .ghost-btn,
.preview-actions .primary-btn {
  flex: 1;
  padding: 15px;
  border-radius: 999px;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 1px;
}
.preview-actions .ghost-btn {
  background: rgba(255, 255, 255, 0.14);
  border: 1.5px solid rgba(255, 255, 255, 0.3);
  color: #fff;
}
.preview-actions .primary-btn {
  background: var(--brand-deep);
  color: #fff;
}
.loading-card {
  width: 100%;
  max-width: 320px;
  text-align: center;
}
.loading-spinner-wrap {
  display: flex;
  justify-content: center;
  margin-bottom: 22px;
}
.loading-title {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #3a2f28;
}
.loading-flower {
  margin-top: 26px;
  padding: 20px;
  border-radius: 18px;
  background: #faf5ef;
}
.lf-dot {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--brand);
  box-shadow: 0 0 0 5px rgba(255, 92, 122, 0.18);
  margin-bottom: 10px;
}
.lf-dot.foliage {
  background: #43aa8b;
  box-shadow: 0 0 0 5px rgba(67, 170, 139, 0.18);
}
.lf-name {
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 1px;
}
.lf-meaning {
  margin-top: 6px;
  font-size: 13px;
  color: #9a8a7c;
}
.flower-fade-enter-active,
.flower-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.flower-fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}
.flower-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* 进度条 */
.progress-track {
  margin-top: 26px;
  height: 8px;
  border-radius: 999px;
  background: #f0e8de;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #ff7a59, #e83e6b);
  transition: width 0.2s ease;
}
.progress-num {
  margin-top: 12px;
  font-size: 13px;
  color: #9a8a7c;
  font-family: ui-monospace, monospace;
}

/* ===== 教程步骤 ===== */
.topbar {
  position: relative;
  height: calc(var(--safe-top) + 52px);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-top: var(--safe-top);
}
.topbar.dark {
  background: #1c1420;
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
.topbar.dark .back-btn {
  background: rgba(255, 255, 255, 0.12);
}
.capsule-close.light {
  background: rgba(0, 0, 0, 0.05);
  border-color: transparent;
}

.scroll-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 20px calc(var(--safe-bottom) + 20px);
  display: flex;
  flex-direction: column;
}

.step-progress {
  display: flex;
  gap: 6px;
  margin: 4px 0 16px;
}
.sp-seg {
  flex: 1;
  height: 4px;
  border-radius: 999px;
  background: #eadfd3;
  transition: background 0.3s;
}
.sp-seg.done {
  background: #e8a87c;
}
.sp-seg.active {
  background: var(--brand-deep);
}

.step-card {
  flex: 1;
  border-radius: 24px;
  background: #fff;
  padding: 22px 20px;
  box-shadow: 0 10px 28px rgba(90, 60, 40, 0.1);
  display: flex;
  flex-direction: column;
}
.step-count {
  font-size: 11.5px;
  letter-spacing: 2.5px;
  color: var(--brand-deep);
  font-weight: 700;
}
.step-title {
  margin-top: 8px;
  font-size: 24px;
  font-weight: 800;
  letter-spacing: 1.5px;
}
.step-illustration {
  margin-top: 16px;
  border-radius: 18px;
  overflow: hidden;
  aspect-ratio: 4 / 3;
  background: #f4ede4;
}
.step-illustration img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.step-illu-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 20px;
}
.illu-num {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 800;
  color: #5a4a3d;
  box-shadow: 0 4px 12px rgba(90, 60, 40, 0.15);
}
.illu-prompt {
  font-size: 12.5px;
  color: rgba(90, 74, 61, 0.75);
  text-align: center;
}
.step-illu-loading {
  gap: 14px;
}
.illu-spinner {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 3px solid rgba(255, 255, 255, 0.5);
  border-top-color: rgba(90, 74, 61, 0.65);
  animation: illu-spin 0.9s linear infinite;
}
@keyframes illu-spin {
  to {
    transform: rotate(360deg);
  }
}
.step-illustration img {
  animation: illu-fadein 0.35s ease;
}
@keyframes illu-fadein {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
.step-desc {
  margin-top: 16px;
  font-size: 14.5px;
  line-height: 1.8;
  color: #5a4a3d;
}
.step-flowers {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.sf-chip {
  font-size: 12px;
  padding: 5px 12px;
  border-radius: 999px;
  background: rgba(232, 62, 107, 0.09);
  color: var(--brand-deep);
  font-weight: 600;
}

.step-slide-enter-active,
.step-slide-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}
.step-slide-enter-from {
  opacity: 0;
  transform: translateX(30px);
}
.step-slide-leave-to {
  opacity: 0;
  transform: translateX(-30px);
}

.step-actions {
  display: flex;
  gap: 12px;
  margin-top: 18px;
}
.ghost-dark {
  padding: 15px 22px;
  border-radius: 999px;
  border: 1.5px solid #ddd0c0;
  color: #7a6a5c;
  font-size: 15px;
  font-weight: 600;
}
.flex-1 {
  flex: 1;
}
.finish-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

/* ===== 分享 ===== */
.share-body {
  flex: 1;
  overflow-y: auto;
  padding: 10px 22px calc(var(--safe-bottom) + 20px);
  background: linear-gradient(180deg, #1c1420 0%, #17121a 100%);
}
.compare-wrap {
  border-radius: 22px;
  overflow: hidden;
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.5);
  aspect-ratio: 3 / 4;
  background: #000;
}
.compare-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.bgm-section {
  margin-top: 18px;
}
.bgm-title {
  font-size: 13px;
  letter-spacing: 2px;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 10px;
}
.bgm-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.bgm-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.07);
  border: 1.5px solid transparent;
  color: #fff;
  text-align: left;
}
.bgm-item.active {
  border-color: var(--brand);
  background: rgba(232, 62, 107, 0.16);
}
.bgm-note {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.bgm-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.bgm-name {
  font-size: 14.5px;
  font-weight: 600;
}
.bgm-artist {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);
}
.bgm-check {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--brand-deep);
  display: flex;
  align-items: center;
  justify-content: center;
}

.share-actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
}
.ghost-btn {
  flex: 1;
  padding: 15px 0;
  border-radius: 999px;
  border: 1.5px solid rgba(255, 255, 255, 0.4);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
}
.douyin-btn {
  flex: 1.4;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: linear-gradient(135deg, #161823, #000);
  border: 1.5px solid rgba(255, 255, 255, 0.35);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.5);
}
</style>
