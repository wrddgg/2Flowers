<template>
  <div class="feed-page">
    <!-- 视频列表：上下滑动切换 -->
    <div
      class="video-track"
      :style="{ transform: `translateY(-${currentIndex * 100}%)` }"
      @touchstart="onTouchStart"
      @touchmove="onTouchMove"
      @touchend="onTouchEnd"
    >
      <div v-for="(v, i) in videos" :key="i" class="video-item">
        <video
          :ref="(el) => (videoRefs[i] = el)"
          :src="v.url"
          class="video"
          loop
          muted
          playsinline
          webkit-playsinline
          x5-playsinline
          x5-video-player-type="h5-page"
          x-webkit-airplay="allow"
          disablepictureinpicture
          disableremoteplayback
          controlslist="nodownload nofullscreen noremoteplayback"
          preload="auto"
          @click="togglePlay(i)"
          @error="onVideoError(i)"
        ></video>
        <!-- 视频加载失败降级封面 -->
        <div v-if="v.failed" class="video-fallback" @click="togglePlay(i)">
          <div class="fallback-bg" :style="{ background: v.fallbackBg }"></div>
          <p class="fallback-text">视频加载失败，点击重试</p>
        </div>

        <!-- 底部文案 -->
        <div class="video-meta">
          <p class="author">@{{ v.author }}</p>
          <p class="desc">{{ v.desc }}</p>
        </div>

        <!-- 暂停态：中央播放图标 + 右下"万物生花"标签 -->
        <transition name="pause-pop">
          <div v-if="pausedIndex === i" class="pause-layer" @click.stop="togglePlay(i)">
            <svg class="pause-icon" viewBox="0 0 24 24" fill="rgba(255,255,255,0.85)">
              <path d="M8 5v14l11-7z" />
            </svg>
            <!-- 照抄图2样式：半透明黑底胶囊 + 图标，文字"万物生花"，可点击进入 -->
            <button class="wwsh-tag" @click.stop="enterWwsh">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#fff" stroke-width="1.8">
                <path d="M12 22V12" />
                <path d="M12 12c0-3 2.5-5 5.5-5 0 3-2.5 5-5.5 5z" fill="rgba(255,255,255,.25)" />
                <path d="M12 12c0-3-2.5-5-5.5-5 0 3 2.5 5 5.5 5z" fill="rgba(255,255,255,.25)" />
                <circle cx="12" cy="6.5" r="2.6" fill="rgba(255,255,255,.25)" />
              </svg>
              <span>万物生花</span>
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#fff" stroke-width="2.4">
                <path d="M9 6l6 6-6 6" />
              </svg>
            </button>
          </div>
        </transition>
      </div>
    </div>

    <!-- 右侧操作栏 -->
    <div class="action-bar">
      <!-- 音量开关 -->
      <button class="action-item" @click="toggleMute">
        <svg v-if="muted" viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="#fff" stroke-width="1.8">
          <path d="M11 5L6 9H3v6h3l5 4V5z" fill="#fff" stroke="none"/>
          <path d="M16 9l5 6M21 9l-5 6" stroke-linecap="round"/>
        </svg>
        <svg v-else viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="#fff" stroke-width="1.8">
          <path d="M11 5L6 9H3v6h3l5 4V5z" fill="#fff" stroke="none"/>
          <path d="M15.5 8.5a5 5 0 010 7M18.5 6a9 9 0 010 12" stroke-linecap="round"/>
        </svg>
        <span>{{ muted ? '静音' : '有声' }}</span>
      </button>
      <button class="action-item">
        <svg viewBox="0 0 24 24" width="30" height="30" fill="#fff">
          <path d="M12 21s-7.5-4.7-10-9.3C.4 8.6 2.3 5 5.7 5c2 0 3.4 1.1 4.3 2.4h4c.9-1.3 2.3-2.4 4.3-2.4 3.4 0 5.3 3.6 3.7 6.7C19.5 16.3 12 21 12 21z" opacity=".95"/>
        </svg>
        <span>12.4w</span>
      </button>
      <button class="action-item">
        <svg viewBox="0 0 24 24" width="30" height="30" fill="#fff">
          <path d="M4 4h16v12H8l-4 4V4z" opacity=".95"/>
        </svg>
        <span>1.2w</span>
      </button>
      <button class="action-item">
        <svg viewBox="0 0 24 24" width="30" height="30" fill="#fff">
          <path d="M14 9V5l7 7-7 7v-4c-5 0-8.5 1.6-11 5 1-5 4-9 11-11z" opacity=".95"/>
        </svg>
        <span>分享</span>
      </button>
      <!-- 分享下方：万物生花入口（圆形小花按钮） -->
      <button class="action-item wwsh-entry" @click="enterWwsh">
        <span class="wwsh-entry-icon">
          <img src="/icon.png" class="wwsh-entry-img" alt="万物生花" />
        </span>
        <span>万物生花</span>
      </button>
    </div>

    <!-- 顶部：小程序圆形退出按钮（只保留圆叉） -->
    <button class="capsule-close" @click="exitMiniProgram" aria-label="退出">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round">
        <path d="M6 6l12 12M18 6L6 18" />
      </svg>
    </button>

    <!-- 顶部进度点 -->
    <div class="video-dots">
      <span v-for="(v, i) in videos" :key="i" class="dot" :class="{ active: i === currentIndex }"></span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { store, goTo, resetFlow } from '../store'

const videos = ref([
  {
    url: '/videos/1.mp4',
    author: '山海旅人',
    desc: '日落把海面烧成了橘子汽水🍊 #黄昏 #治愈系风景',
    failed: false,
    fallbackBg: 'linear-gradient(180deg,#2b1055 0%,#7597de 55%,#e8a87c 100%)'
  },
  {
    url: '/videos/2.mp4',
    author: '花事未了',
    desc: '风一吹，整片山谷都在开花🌸 #春天 #花海',
    failed: false,
    fallbackBg: 'linear-gradient(180deg,#134e5e 0%,#71b280 60%,#f7dc6f 100%)'
  }
])

const currentIndex = ref(0)
const pausedIndex = ref(-1)
const videoRefs = ref([])
const muted = ref(true)

function toggleMute() {
  muted.value = !muted.value
  videoRefs.value.forEach((el) => {
    if (el) el.muted = muted.value
  })
}

let touchStartY = 0
let touchDeltaY = 0
let switching = false

function onTouchStart(e) {
  touchStartY = e.touches[0].clientY
  touchDeltaY = 0
}

function onTouchMove(e) {
  touchDeltaY = e.touches[0].clientY - touchStartY
}

function onTouchEnd() {
  if (switching) return
  const threshold = 70
  if (touchDeltaY < -threshold && currentIndex.value < videos.value.length - 1) {
    switchTo(currentIndex.value + 1)
  } else if (touchDeltaY > threshold && currentIndex.value > 0) {
    switchTo(currentIndex.value - 1)
  }
  touchDeltaY = 0
}

async function switchTo(i) {
  switching = true
  pauseAll()
  currentIndex.value = i
  pausedIndex.value = -1
  await nextTick()
  playCurrent()
  setTimeout(() => (switching = false), 400)
}

function playCurrent() {
  const el = videoRefs.value[currentIndex.value]
  if (el) {
    el.currentTime = el.currentTime || 0
    el.play().catch(() => {
      pausedIndex.value = currentIndex.value
    })
  }
}

function pauseAll() {
  videoRefs.value.forEach((el) => el && el.pause())
}

function togglePlay(i) {
  const el = videoRefs.value[i]
  if (!el || videos.value[i].failed) {
    // 重试加载
    if (videos.value[i].failed) {
      videos.value[i].failed = false
      nextTick(() => videoRefs.value[i]?.load())
    }
    return
  }
  if (el.paused) {
    el.play().catch(() => {})
    pausedIndex.value = -1
  } else {
    el.pause()
    pausedIndex.value = i
    captureSnapshot(el)
  }
}

/* 截取视频当前帧，作为万物生花的默认画面来源 */
function captureSnapshot(el) {
  try {
    const canvas = document.createElement('canvas')
    canvas.width = el.videoWidth || 720
    canvas.height = el.videoHeight || 1280
    canvas.getContext('2d').drawImage(el, 0, 0, canvas.width, canvas.height)
    store.videoSnapshot = canvas.toDataURL('image/jpeg', 0.85)
  } catch (err) {
    // 跨域导致 canvas 污染时，静默失败，SourcePage 会用渐变占位图
    store.videoSnapshot = ''
  }
}

function onVideoError(i) {
  videos.value[i].failed = true
}

function enterWwsh() {
  // 若当前在播放，先暂停并尝试取帧
  const el = videoRefs.value[currentIndex.value]
  if (el && !el.paused) {
    el.pause()
    pausedIndex.value = currentIndex.value
    captureSnapshot(el)
  }
  goTo('source')
}

function exitMiniProgram() {
  // 小程序退出 → 返回刷视频界面（当前已在刷视频页，回到第一个视频）
  resetFlow()
  pauseAll()
  currentIndex.value = 0
  pausedIndex.value = -1
  nextTick(() => playCurrent())
}

onMounted(() => {
  playCurrent()
})

onBeforeUnmount(() => {
  pauseAll()
})
</script>

<style scoped>
.feed-page {
  position: absolute;
  inset: 0;
  background: #000;
  overflow: hidden;
}

.video-track {
  height: 100%;
  transition: transform 0.35s cubic-bezier(0.25, 0.8, 0.3, 1);
}

.video-item {
  position: relative;
  height: 100%;
  width: 100%;
  overflow: hidden;
}

.video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  background: #000;
  /* 防止小米/国产浏览器把视频提升为原生全屏层 */
  pointer-events: auto;
  transform: translateZ(0);
}
/* 隐藏视频原生控件，强制走页面内自定义交互 */
.video::-webkit-media-controls {
  display: none !important;
}
.video::-webkit-media-controls-start-playback-button {
  display: none !important;
}

.video-fallback {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.fallback-bg {
  position: absolute;
  inset: 0;
}
.fallback-text {
  position: relative;
  color: rgba(255, 255, 255, 0.85);
  font-size: 14px;
  padding: 10px 20px;
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 999px;
}

.video-meta {
  position: absolute;
  left: 14px;
  bottom: calc(var(--safe-bottom) + 34px);
  right: 90px;
  color: #fff;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.5);
}
.author {
  font-weight: 700;
  font-size: 16px;
  margin-bottom: 8px;
}
.desc {
  font-size: 14px;
  line-height: 1.5;
  opacity: 0.95;
}

/* 右侧操作栏 */
.action-bar {
  position: absolute;
  right: 8px;
  bottom: calc(var(--safe-bottom) + 90px);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  z-index: 20;
}
.action-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: #fff;
  font-size: 12px;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
}
.action-item:active {
  transform: scale(0.9);
}

.wwsh-entry-icon {
  width: 46px;
  height: 46px;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: pulse-soft 2.4s ease-in-out infinite;
}
.wwsh-entry-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  /* 白色花纹，加投影保证在视频上清晰 */
  filter: drop-shadow(0 1px 3px rgba(0, 0, 0, 0.65)) drop-shadow(0 0 2px rgba(0, 0, 0, 0.45));
}

/* 暂停层 */
.pause-layer {
  position: absolute;
  inset: 0;
  z-index: 15;
  display: flex;
  align-items: center;
  justify-content: center;
}
.pause-icon {
  width: 84px;
  height: 84px;
  filter: drop-shadow(0 2px 10px rgba(0, 0, 0, 0.4));
}

/* 万物生花标签：暂停图标右下方，照抄图2胶囊样式 */
.wwsh-tag {
  position: absolute;
  top: 50%;
  left: calc(50% + 26px);
  transform: translateY(58px);
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px 8px 10px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(10px);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 0.5px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
}
.wwsh-tag:active {
  transform: translateY(58px) scale(0.95);
  background: rgba(232, 62, 107, 0.75);
}

.pause-pop-enter-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.pause-pop-leave-active {
  transition: opacity 0.15s ease;
}
.pause-pop-enter-from,
.pause-pop-leave-to {
  opacity: 0;
}
.pause-pop-enter-from .wwsh-tag {
  transform: translateY(68px);
}

.video-dots {
  position: absolute;
  top: calc(var(--safe-top) + 16px);
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 6px;
  z-index: 20;
}
.dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.35);
  transition: all 0.3s;
}
.dot.active {
  background: #fff;
  width: 14px;
  border-radius: 3px;
}
</style>
