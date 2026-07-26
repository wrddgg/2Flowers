<template>
  <div class="analysis-page">
    <!-- 背景：用户提交的原图 + 深色渐变蒙层 -->
    <div class="bg">
      <img v-if="store.sourceImage" :src="store.sourceImage" class="bg-img" alt="" />
      <div v-else class="bg-fallback"></div>
      <div class="bg-mask"></div>
    </div>

    <button class="capsule-close" @click="exitToFeed" aria-label="退出">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round">
        <path d="M6 6l12 12M18 6L6 18" />
      </svg>
    </button>

    <div class="content" v-if="a">
      <!-- 上半：AI 解读 -->
      <section class="interpret">
        <h2 class="title fade-up">「{{ selectedOption?.label || a.title }}」</h2>

        <div class="info-card fade-up" style="animation-delay:.12s">
          <div class="row">
            <span class="label">风格</span>
            <span class="value">{{ a.style }}</span>
          </div>
          <div class="row">
            <span class="label">情绪</span>
            <span class="value">{{ a.mood }}</span>
          </div>
          <div class="row palette-row">
            <span class="label">色调</span>
            <div class="palette">
              <span
                v-for="(c, i) in a.palette"
                :key="i"
                class="swatch"
                :style="{ background: c }"
                :title="c"
              ></span>
            </div>
          </div>
          <div class="row content-row">
            <span class="label">画面</span>
            <p class="desc">{{ a.content }}</p>
          </div>
        </div>

        <div v-if="options.length" class="choice-wrap fade-up" style="animation-delay:.16s">
          <p class="choice-label">转译视角</p>
          <div class="choice-list">
            <button
              v-for="option in options"
              :key="option.option_id"
              class="choice-chip"
              :class="{ active: option.option_id === selectedInterpretationId }"
              @click="selectedInterpretationId = option.option_id"
            >
              {{ option.label }}
            </button>
          </div>
          <p class="choice-desc">{{ selectedOption?.explanation || a.planner_summary }}</p>
        </div>
      </section>

      <!-- 场景与风格选择 -->
      <section class="preset-picker fade-up" style="animation-delay:.18s">
        <div class="picker-block">
          <div class="picker-head">
            <p class="picker-title">这束花用在什么场景？</p>
            <span class="picker-tip">决定花量与礼仪感</span>
          </div>
          <div class="chip-row">
            <button
              v-for="s in sceneOptions"
              :key="s"
              class="chip"
              :class="{ active: selectedScene === s }"
              @click="selectedScene = s"
            >{{ s }}</button>
          </div>
        </div>
        <div class="picker-block">
          <div class="picker-head">
            <p class="picker-title">选择花束风格</p>
            <span class="picker-tip">决定形态与留白</span>
          </div>
          <div class="chip-row">
            <button
              v-for="s in styleOptions"
              :key="s"
              class="chip"
              :class="{ active: selectedStyle === s }"
              @click="selectedStyle = s"
            >{{ s }}</button>
          </div>
        </div>
      </section>

      <!-- 下半：保留 demo 的"日落为礼"引导区 -->
      <section class="bridge fade-up" style="animation-delay:.2s">
        <div class="bridge-card">
          <p class="bridge-title">{{ selectedOption?.label || a.title }}</p>
          <p class="bridge-sub">正在为你匹配花材，生成一束只属于这个画面的花</p>
          <button class="primary-btn" :disabled="generating" @click="generate">
            {{ generating ? '' : `生成「${selectedScene} · ${selectedStyle}」花束` }}
            <span v-if="generating" class="btn-loading"><span class="spinner"></span></span>
          </button>
          <p v-if="generating" class="gen-hint">{{ genHintText }}</p>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'
import { store, goTo, exitToFeed } from '../store'
import { generateBouquet, searchReferences } from '../api'

const generating = ref(false)

// 生成中循环提示
const genHints = ['正在挑选花材…', '正在设计构图…', '正在综合配色…']
const genHintIndex = ref(0)
const genHintText = computed(() => genHints[genHintIndex.value])
let genHintTimer = null
function startGenHint() {
  genHintIndex.value = 0
  clearInterval(genHintTimer)
  genHintTimer = setInterval(() => {
    genHintIndex.value = (genHintIndex.value + 1) % genHints.length
  }, 1600)
}
function stopGenHint() {
  clearInterval(genHintTimer)
  genHintTimer = null
}
onBeforeUnmount(stopGenHint)
const a = computed(() => store.analysis)
const options = computed(() => a.value?.interpretation_options || [])
const selectedInterpretationId = computed({
  get: () => store.selectedInterpretationId || a.value?.recommended_interpretation_id || '',
  set: (value) => {
    store.selectedInterpretationId = value
  }
})
const selectedOption = computed(() =>
  options.value.find((item) => item.option_id === selectedInterpretationId.value) || options.value[0] || null
)

// 场景与风格选项（与后端 ScenePreset / StylePreset 枚举一致）
const sceneOptions = ['礼宾赠礼', '庆祝纪念', '恋人赠礼', '日常居家']
const styleOptions = ['东方留白', '法式浪漫', '清新自然', '现代艺术']
const selectedScene = ref(sceneOptions[0])
const selectedStyle = ref(styleOptions[0])

async function generate() {
  if (generating.value) return
  generating.value = true
  startGenHint()
  try {
    store.references = await searchReferences({
      analysis: store.analysis,
      selectedInterpretationId: selectedInterpretationId.value
    })
    store.bouquet = await generateBouquet({
      analysis: store.analysis,
      selectedInterpretationId: selectedInterpretationId.value,
      references: store.references,
      selectedScene: selectedScene.value,
      selectedStyle: selectedStyle.value
    })
    store.selectedBouquetIndex = 0
    store.editedBouquetImage = ''
    store.emotion = null
    goTo('bouquet')
  } finally {
    stopGenHint()
    generating.value = false
  }
}
</script>

<style scoped>
.analysis-page {
  position: absolute;
  inset: 0;
  overflow: hidden;
  color: #fff;
}

.bg {
  position: absolute;
  inset: 0;
}
.bg-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.bg-fallback {
  width: 100%;
  height: 100%;
  background: linear-gradient(180deg, #2b1055 0%, #7597de 55%, #e8a87c 100%);
}
.bg-mask {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    180deg,
    rgba(0, 0, 0, 0.25) 0%,
    rgba(0, 0, 0, 0.45) 40%,
    rgba(10, 6, 12, 0.88) 78%,
    rgba(10, 6, 12, 0.96) 100%
  );
}

.content {
  position: relative;
  height: 100%;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: calc(var(--safe-top) + 64px) 22px calc(var(--safe-bottom) + 24px);
  display: flex;
  flex-direction: column;
  gap: 18px;
}
/* 内容不足一屏时靠底对齐（保持原视觉）；超过一屏时自然从顶部排开、可滚动 */
.content::before {
  content: '';
  margin-top: auto;
}

.kicker {
  font-size: 13px;
  letter-spacing: 3px;
  color: rgba(255, 255, 255, 0.65);
}
.title {
  margin-top: 8px;
  /* 一行显示完，字号随屏宽自适应缩放 */
  font-size: clamp(18px, 6.5vw, 38px);
  font-weight: 800;
  letter-spacing: clamp(0.5px, 0.8vw, 3px);
  line-height: 1.25;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-shadow: 0 2px 18px rgba(0, 0, 0, 0.45);
}

.info-card {
  margin-top: 16px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(255, 255, 255, 0.16);
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.choice-wrap {
  margin-top: 14px;
}

.choice-label {
  font-size: 12px;
  letter-spacing: 2px;
  color: rgba(255, 255, 255, 0.62);
}

.choice-list {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.choice-chip {
  padding: 9px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.16);
  color: rgba(255, 255, 255, 0.86);
  font-size: 12.5px;
}

.choice-chip.active {
  background: rgba(255, 255, 255, 0.92);
  color: #1e1a1d;
}

.choice-desc {
  margin-top: 10px;
  font-size: 12.5px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.72);
}
.row {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}
.label {
  flex-shrink: 0;
  width: 40px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  letter-spacing: 2px;
  padding-top: 1px;
}
.value {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.5px;
}
.palette {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.swatch {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  border: 1.5px solid rgba(255, 255, 255, 0.35);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
}
.desc {
  flex: 1;
  font-size: 14px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.88);
}

.preset-picker {
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(255, 255, 255, 0.14);
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.picker-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.picker-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}
.picker-title {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 1px;
  color: rgba(255, 255, 255, 0.92);
}
.picker-tip {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  letter-spacing: 0.5px;
  flex-shrink: 0;
}
.chip-row {
  display: flex;
  gap: 6px;
  flex-wrap: nowrap;
}
.chip {
  flex: 1 1 0;
  min-width: 0;
  padding: 8px 4px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.16);
  color: rgba(255, 255, 255, 0.86);
  font-size: clamp(11px, 3.1vw, 13px);
  text-align: center;
  white-space: nowrap;
  transition: all 0.18s ease;
}
.chip.active {
  background: rgba(255, 255, 255, 0.92);
  color: #1e1a1d;
  border-color: rgba(255, 255, 255, 0.92);
  font-weight: 600;
}

.bridge-card {
  border-radius: 22px;
  background: linear-gradient(160deg, rgba(61, 107, 87, 0.32), rgba(45, 74, 62, 0.42));
  border: 1px solid rgba(245, 241, 232, 0.25);
  backdrop-filter: blur(14px);
  padding: 20px 18px;
}
.bridge-title {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 1px;
}
.bridge-sub {
  margin: 8px 0 16px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.72);
  line-height: 1.6;
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
.gen-hint {
  margin-top: 10px;
  text-align: center;
  font-size: 12.5px;
  color: rgba(255, 255, 255, 0.6);
  letter-spacing: 1px;
}
</style>
