<template>
  <div class="card-page">
    <header class="topbar">
      <button class="back-btn" @click="goTo('bouquet')" aria-label="返回">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#2d4a3e" stroke-width="2.2" stroke-linecap="round">
          <path d="M15 5l-7 7 7 7" />
        </svg>
      </button>
      <button class="remake-btn" @click="onRemake">重新制作</button>
      <button class="capsule-close light" @click="exitToFeed" aria-label="退出">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#2d4a3e" stroke-width="2.2" stroke-linecap="round">
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>
    </header>

    <div class="scroll-body">
      <!-- 花束卡片 -->
      <div class="bouquet-card fade-up">
        <!-- 卡头：品牌 -->
        <div class="card-top">
          <span class="card-brand">
            <img src="/icon.png" class="card-brand-icon" alt="" />
            万物生花
          </span>
          <span class="card-no">NO.{{ cardNo }}</span>
        </div>

        <!-- 花束图 -->
        <div class="card-img">
          <img v-if="displayImage" :src="displayImage" alt="花束" />
          <BouquetSvg v-else />
        </div>

        <!-- 灵感来源 -->
        <div class="card-body">
          <p class="cb-kicker">灵感来自</p>
          <h3 class="cb-title">「{{ a?.title || '未命名画面' }}」</h3>
          <span v-if="store.isRemakeCard" class="remake-badge">复刻花束</span>
          <div class="cb-palette" v-if="a?.palette">
            <span v-for="(c, i) in a.palette" :key="i" :style="{ background: c }"></span>
          </div>

          <div class="cb-flowers" v-if="b?.flowers">
            <span v-for="f in mainFlowers" :key="f.name" class="cb-chip">{{ f.name }}</span>
          </div>

          <p class="cb-meaning">{{ cardMeaning }}</p>
        </div>

        <!-- 卡尾 -->
        <div class="card-foot">
          <span>{{ today }}</span>
          <span class="foot-line"></span>
          <span>把任何画面，变成一束花</span>
        </div>
      </div>

      <div v-if="emotion" class="emotion-card fade-up" style="animation-delay:.08s">
        <p class="emotion-title">现实承接建议</p>
        <p class="emotion-copy">{{ emotion.save_card.copy }}</p>
        <p class="emotion-target">{{ emotion.gift_card.target }}</p>
        <p class="emotion-reason">{{ emotion.gift_card.reason }}</p>
      </div>

      <!-- 操作 -->
      <div class="actions fade-up" style="animation-delay:.12s">
        <button class="ghost-btn" @click="saveCard">保存卡片</button>
        <button class="primary-btn" @click="goTo('remake-plan')">想要制作</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { store, goTo, exitToFeed, resetFlow } from '../store'
import BouquetSvg from '../components/BouquetSvg.vue'
import { buildEmotion } from '../api'

const a = computed(() => store.analysis)
const b = computed(() => store.bouquet?.results?.[store.selectedBouquetIndex] || null)
const displayImage = computed(() => {
  const rid = b.value?.result_id
  return (rid && store.editedBouquetImages?.[rid]) || b.value?.bouquet_image || ''
})
const emotion = computed(() => store.emotion)

const cardNo = computed(() => String(Math.floor(Math.random() * 9000) + 1000))
const today = new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })

const mainFlowers = computed(() => (b.value?.flowers || []).filter((f) => f.category === 'flower').slice(0, 4))

const cardMeaning = computed(() => {
  const flowers = b.value?.flowers || []
  if (!flowers.length) return ''
  const main = flowers[0]
  return `${main.name}说：${main.meaning}。愿这束花，替你留住那天的光。`
})

function saveCard() {
  // 演示：真实场景用 html2canvas 或后端接口4生成图片保存
  alert('卡片已保存到相册（演示）')
}

function onRemake() {
  if (window.confirm('确定要重新制作吗？当前花束将被清除并回到开始。')) {
    resetFlow()
  }
}

onMounted(async () => {
  if (!b.value || store.emotion) return
  try {
    store.emotion = await buildEmotion({
      resultId: b.value.result_id,
      mode: a.value?.mode_result?.detected_mode || 'scene',
      voiceContext: store.voiceText || ''
    })
  } catch (error) {
    console.warn(error)
  }
})
</script>

<style scoped>
.card-page {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(100% 50% at 50% 0%, #e8dcc8 0%, transparent 65%),
    linear-gradient(180deg, #f5f1e8 0%, #ece5d5 100%);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  color: var(--ink);
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
  padding: 4px 26px calc(var(--safe-bottom) + 22px);
  display: flex;
  flex-direction: column;
}

.bouquet-card {
  border-radius: 26px;
  background: linear-gradient(170deg, #fffdf9 0%, #f7efe6 100%);
  color: var(--ink);
  overflow: hidden;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45);
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 18px 12px;
}
.card-brand {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 2px;
  color: var(--brand-deep);
}
.card-brand-icon {
  width: 22px;
  height: 22px;
  object-fit: contain;
  /* 白色花纹 -> 墨绿 */
  filter: brightness(0) saturate(100%) invert(27%) sepia(12%) saturate(1400%) hue-rotate(95deg) brightness(0.9) contrast(1.05);
}
.card-no {
  font-size: 11px;
  letter-spacing: 1.5px;
  color: #b3a493;
  font-family: ui-monospace, monospace;
}

.card-img {
  margin: 0 16px;
  border-radius: 18px;
  overflow: hidden;
  aspect-ratio: 1 / 1;
  background: #efe9e1;
}
.card-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.card-body {
  padding: 18px 20px 6px;
  text-align: center;
}
.cb-kicker {
  font-size: 11.5px;
  letter-spacing: 3px;
  color: #b3a493;
}
.cb-title {
  margin-top: 6px;
  font-size: 24px;
  font-weight: 800;
  letter-spacing: 2px;
}
.remake-badge {
  display: inline-block;
  margin-top: 8px;
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(61, 107, 87, 0.12);
  border: 1px solid rgba(61, 107, 87, 0.3);
  color: var(--brand-deep);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
}
.cb-palette {
  margin-top: 12px;
  display: flex;
  justify-content: center;
  gap: 7px;
}
.cb-palette span {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2px solid #fff;
  box-shadow: 0 2px 6px rgba(90, 60, 40, 0.2);
}
.cb-flowers {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}
.cb-chip {
  font-size: 12px;
  padding: 5px 12px;
  border-radius: 999px;
  background: rgba(61, 107, 87, 0.1);
  color: var(--brand-deep);
  font-weight: 600;
}
.cb-meaning {
  margin: 14px auto 4px;
  max-width: 260px;
  font-size: 13px;
  line-height: 1.8;
  color: #7a6a5c;
}

.card-foot {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 12px 18px 18px;
  font-size: 11px;
  letter-spacing: 1.5px;
  color: #b3a493;
}
.foot-line {
  width: 26px;
  height: 1px;
  background: #ddd0c0;
}

.actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
}

.emotion-card {
  margin-top: 16px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(10px);
  padding: 16px;
  color: #5d4e41;
}

.emotion-title {
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 2px;
  color: var(--brand-deep);
}

.emotion-copy,
.emotion-reason {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
}

.emotion-target {
  margin-top: 10px;
  font-size: 13px;
  font-weight: 700;
}

.emotion-options {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.emotion-option {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  background: rgba(255, 255, 255, 0.8);
  border: 1.5px solid transparent;
  border-radius: 14px;
  padding: 12px;
  text-align: left;
  transition: all 0.18s ease;
}
.emotion-option.active {
  border-color: var(--brand-deep);
  background: rgba(61, 107, 87, 0.08);
}
.eo-radio {
  margin-top: 3px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 1.5px solid #c4b6a4;
  flex-shrink: 0;
  position: relative;
  transition: border-color 0.18s ease;
}
.emotion-option.active .eo-radio {
  border-color: var(--brand-deep);
}
.emotion-option.active .eo-radio::after {
  content: '';
  position: absolute;
  inset: 3px;
  border-radius: 50%;
  background: var(--brand-deep);
}
.eo-text {
  flex: 1;
}

.eo-title {
  font-size: 13px;
  font-weight: 700;
}

.eo-sub,
.eo-reason {
  margin-top: 4px;
  font-size: 12px;
  color: #7d6d5f;
  line-height: 1.6;
}
.ghost-btn {
  flex: 1;
  padding: 15px 0;
  border-radius: 999px;
  border: 1.5px solid rgba(45, 74, 62, 0.35);
  color: var(--brand-deep);
  font-size: 15px;
  font-weight: 600;
}
.ghost-btn:active {
  background: rgba(45, 74, 62, 0.08);
}
.actions .primary-btn {
  flex: 1.4;
}

.remake-btn {
  position: absolute;
  top: calc(var(--safe-top) + 12px);
  right: 56px;
  height: 34px;
  padding: 0 14px;
  border-radius: 999px;
  border: none;
  background: rgba(45, 74, 62, 0.08);
  color: #2d4a3e;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}
</style>
