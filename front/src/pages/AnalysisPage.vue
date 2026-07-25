<template>
  <div class="analysis-page">
    <!-- 背景：用户提交的原图 + 深色渐变蒙层 -->
    <div class="bg">
      <img v-if="store.sourceImage" :src="store.sourceImage" class="bg-img" alt="" />
      <div v-else class="bg-fallback"></div>
      <div class="bg-mask"></div>
    </div>

    <button class="capsule-close" @click="goTo('feed')" aria-label="退出">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round">
        <path d="M6 6l12 12M18 6L6 18" />
      </svg>
    </button>

    <div class="content" v-if="a">
      <!-- 上半：AI 解读 -->
      <section class="interpret">
        <p class="kicker fade-up">AI 为这幅画面起名</p>
        <h2 class="title fade-up" style="animation-delay:.06s">「{{ selectedOption?.label || a.title }}」</h2>

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

      <!-- 下半：保留 demo 的"日落为礼"引导区 -->
      <section class="bridge fade-up" style="animation-delay:.2s">
        <div class="bridge-card">
          <p class="bridge-title">以「{{ selectedOption?.label || a.title }}」为灵感</p>
          <p class="bridge-sub">AI 将为你匹配花材，生成一束只属于这个画面的花</p>
          <button class="primary-btn" :disabled="generating" @click="generate">
            {{ generating ? '' : '生成花束' }}
            <span v-if="generating" class="btn-loading"><span class="spinner"></span></span>
          </button>
          <p v-if="generating" class="gen-hint">正在挑选花材、构图、配色…</p>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { store, goTo } from '../store'
import { generateBouquet, searchReferences } from '../api'

const generating = ref(false)
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

async function generate() {
  if (generating.value) return
  generating.value = true
  try {
    store.references = await searchReferences({
      analysis: store.analysis,
      selectedInterpretationId: selectedInterpretationId.value
    })
    store.bouquet = await generateBouquet({
      analysis: store.analysis,
      selectedInterpretationId: selectedInterpretationId.value,
      references: store.references
    })
    store.selectedBouquetIndex = 0
    store.editedBouquetImage = ''
    store.emotion = null
    goTo('bouquet')
  } finally {
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
  padding: calc(var(--safe-top) + 64px) 22px calc(var(--safe-bottom) + 24px);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 18px;
}

.kicker {
  font-size: 13px;
  letter-spacing: 3px;
  color: rgba(255, 255, 255, 0.65);
}
.title {
  margin-top: 8px;
  font-size: 38px;
  font-weight: 800;
  letter-spacing: 3px;
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
