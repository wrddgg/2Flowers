<template>
  <div class="bouquet-page">
    <header class="topbar">
      <button class="back-btn" @click="goTo('analysis')" aria-label="返回">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#1a1a1a" stroke-width="2.2" stroke-linecap="round">
          <path d="M15 5l-7 7 7 7" />
        </svg>
      </button>
      <span class="topbar-title">你的专属花束</span>
      <button class="capsule-close light" @click="exitToFeed" aria-label="退出">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#1a1a1a" stroke-width="2.2" stroke-linecap="round">
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>
    </header>

    <div class="scroll-body" v-if="currentResult">
      <section class="variant-section">
        <p class="section-title">三版生花方案</p>
        <div class="variant-list">
          <button
            v-for="(item, i) in bouquetResults"
            :key="item.result_id"
            class="variant-chip"
            :class="{ active: i === selectedIndex }"
            @click="selectVariant(i)"
          >
            {{ item.title }}
          </button>
        </div>
      </section>

      <!-- 花束图 + 坐标标签 -->
      <div class="bouquet-stage fade-up">
        <div ref="imgBox" class="bouquet-img-box">
          <img v-if="displayImage" :src="displayImage" class="bouquet-img" alt="花束" />
          <BouquetSvg v-else />
          <!-- 按后端视觉模型返回的 0-1 坐标，标签精准贴在花朵旁边 -->
          <button
            v-for="(f, i) in currentResult.flowers"
            :key="f.flower_id || f.name"
            class="flower-tag"
            :class="[`side-${f.label_side || 'right'}`, { active: i === activeIndex, foliage: f.category === 'foliage' }]"
            :style="tagStyle(f)"
            @click="selectFlower(i)"
          >
            <span class="tag-dot"></span>
            <span class="tag-name">{{ f.name }}</span>
          </button>
        </div>
      </div>

      <!-- 方案生成依据：为什么这样生成 -->
      <section class="why-section" v-if="hasBasis">
        <p class="why-title">为什么这样生成</p>
        <p class="why-text" v-if="currentResult.explanation">{{ currentResult.explanation }}</p>
        <div class="why-rows">
          <div class="why-row" v-if="currentResult.fit_scenes?.length">
            <span class="why-label">适合场景</span>
            <span class="why-value">{{ currentResult.fit_scenes.join('、') }}</span>
          </div>
          <div class="why-row" v-if="currentResult.usage_goal">
            <span class="why-label">用途目的</span>
            <span class="why-value">{{ currentResult.usage_goal }}</span>
          </div>
          <div class="why-row" v-if="currentResult.reality_advice">
            <span class="why-label">现实承接</span>
            <span class="why-value">{{ currentResult.reality_advice }}</span>
          </div>
        </div>
      </section>

      <!-- 当前选中花详情卡 -->
      <transition name="flower-switch" mode="out-in">
        <div class="flower-detail fade-up" :key="active.name" v-if="active">
          <div class="fd-head">
            <div>
              <p class="fd-name">{{ active.name }}</p>
              <p class="fd-role">{{ active.role }} · {{ active.function }}</p>
            </div>
            <span class="fd-confidence">匹配度 {{ Math.round(active.confidence * 100) }}%</span>
          </div>
          <p class="fd-meaning">花语：{{ active.meaning }}</p>
        </div>
      </transition>

      <!-- 参考图片：小标签，点击弹窗看大图 -->
      <section class="ref-section" v-if="currentResult.reference_used?.length">
        <p class="section-title">生成参考</p>
        <div class="ref-chips">
          <button
            v-for="ref in currentResult.reference_used"
            :key="ref.reference_id"
            class="ref-chip"
            @click="openRefPreview(ref)"
          >
            <img :src="ref.cover_url" class="ref-chip-thumb" alt="" />
          </button>
        </div>
      </section>

      <!-- 花卉列表 + 花语 -->
      <section class="list-section">
        <p class="section-title">花材清单与花语</p>
        <button
          v-for="(f, i) in currentResult.flowers"
          :key="f.name"
          class="flower-row"
          :class="{ active: i === activeIndex }"
          @click="selectFlower(i)"
        >
          <span class="fr-index" :class="{ foliage: f.category === 'foliage' }">{{ i + 1 }}</span>
          <span class="fr-main">
            <span class="fr-name">{{ f.name }} <em>{{ f.role }}</em></span>
            <span class="fr-meaning">{{ f.meaning }}</span>
          </span>
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#c9bfb4" stroke-width="2.2">
            <path d="M9 6l6 6-6 6" />
          </svg>
        </button>
      </section>
    </div>

    <!-- 底部 CTA -->
    <footer class="bottom-cta">
      <div class="footer-actions">
        <button class="ghost-btn" @click="goTo('edit')">局部共创编辑</button>
        <button class="primary-btn" @click="goTo('card')">生成花束卡片</button>
      </div>
    </footer>

    <!-- 参考图大图预览弹窗 -->
    <transition name="ref-fade">
      <div v-if="refPreview" class="ref-modal" @click="closeRefPreview">
        <img :src="refPreview.cover_url" class="ref-modal-img" alt="参考图" @click.stop />
        <button class="ref-modal-close" @click="closeRefPreview" aria-label="关闭">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { store, goTo, exitToFeed } from '../store'
import BouquetSvg from '../components/BouquetSvg.vue'

const bouquetResults = computed(() => store.bouquet?.results || [])
const selectedIndex = computed(() => store.selectedBouquetIndex || 0)
const currentResult = computed(() => bouquetResults.value[selectedIndex.value] || null)
const displayImage = computed(() => store.editedBouquetImage || currentResult.value?.bouquet_image || '')
const activeIndex = ref(0)
const active = computed(() => currentResult.value?.flowers[activeIndex.value])
const hasBasis = computed(() =>
  !!(currentResult.value?.explanation || currentResult.value?.fit_scenes?.length ||
     currentResult.value?.usage_goal || currentResult.value?.reality_advice)
)

function selectFlower(i) {
  activeIndex.value = i
}

function selectVariant(i) {
  store.selectedBouquetIndex = i
  store.editedBouquetImage = ''
  activeIndex.value = 0
}

/* 归一化坐标 -> 百分比定位 */
function tagStyle(f) {
  return {
    left: `${f.point[0] * 100}%`,
    top: `${f.point[1] * 100}%`
  }
}

function shortUrl(url) {
  try {
    const u = new URL(url)
    const path = u.pathname.split('/').pop()
    return `${u.host}/…/${path}`
  } catch {
    return url.slice(0, 32) + '…'
  }
}

/* 参考图大图预览 */
const refPreview = ref(null)
function openRefPreview(ref) {
  refPreview.value = ref
}
function closeRefPreview() {
  refPreview.value = null
}
</script>

<style scoped>
.bouquet-page {
  position: absolute;
  inset: 0;
  background: var(--paper);
  display: flex;
  flex-direction: column;
  overflow: hidden;
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
.capsule-close.light {
  background: rgba(0, 0, 0, 0.05);
  border-color: transparent;
}

.scroll-body {
  flex: 1;
  overflow-y: auto;
  padding: 6px 18px 16px;
}

.variant-list {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.variant-chip,
.ghost-btn {
  border-radius: 999px;
  padding: 10px 14px;
  font-size: 12.5px;
  font-weight: 600;
}

.variant-chip {
  background: #ece7e0;
  color: #7d6d5f;
}

.variant-chip.active {
  background: rgba(61, 107, 87, 0.12);
  color: var(--brand-deep);
}

.bouquet-stage {
  border-radius: 24px;
  overflow: hidden;
  box-shadow: 0 14px 34px rgba(90, 60, 40, 0.14);
}
.bouquet-img-box {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  background: #efe9e1;
}
.bouquet-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* 方案生成解读 */
.why-section {
  margin-top: 12px;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(61, 107, 87, 0.06);
  border: 1px solid rgba(61, 107, 87, 0.14);
}
.why-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--brand-deep);
  letter-spacing: 1px;
}
.why-text {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.7;
  color: #5a4a3d;
}
.why-rows {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.why-row {
  display: flex;
  gap: 10px;
  font-size: 12.5px;
  line-height: 1.6;
}
.why-label {
  flex-shrink: 0;
  min-width: 56px;
  font-weight: 700;
  color: var(--brand-deep);
}
.why-value {
  color: #5a4a3d;
}

/* 花标签：锚点在花朵精确位置，标签向一侧偏移贴在花旁 */
.flower-tag {
  position: absolute;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 11px 4px 7px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(4px);
  box-shadow: 0 3px 10px rgba(60, 40, 30, 0.22);
  font-size: 12px;
  font-weight: 600;
  color: #4a3b32;
  white-space: nowrap;
  transition: transform 0.2s ease, background 0.2s ease;
  z-index: 5;
}
.tag-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--accent-deep);
  box-shadow: 0 0 0 3px rgba(212, 133, 154, 0.25);
  flex-shrink: 0;
}
.flower-tag.foliage .tag-dot {
  background: #43aa8b;
  box-shadow: 0 0 0 3px rgba(67, 170, 139, 0.25);
}

/* 按 label_side 把标签偏移到花朵对应一侧（锚点即花的精确坐标） */
.flower-tag.side-right { transform: translate(14px, -50%); }
.flower-tag.side-left  { transform: translate(calc(-100% - 14px), -50%); }
.flower-tag.side-top   { transform: translate(-50%, calc(-100% - 12px)); }
.flower-tag.side-bottom{ transform: translate(-50%, 12px); }

.flower-tag.active {
  background: var(--brand-deep);
  color: #fff;
  z-index: 6;
}
.flower-tag.active .tag-dot {
  background: #fff;
  box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.35);
}
.flower-tag.foliage.active {
  background: #2f8f6f;
}

/* 详情卡 */
.flower-detail {
  margin-top: 16px;
  border-radius: 20px;
  background: #fff;
  padding: 16px 18px;
  box-shadow: 0 8px 22px rgba(90, 60, 40, 0.08);
}
.fd-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
}
.fd-name {
  font-size: 19px;
  font-weight: 800;
  letter-spacing: 1px;
}
.fd-role {
  margin-top: 4px;
  font-size: 12.5px;
  color: #9a8a7c;
}
.fd-confidence {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--brand-deep);
  background: rgba(61, 107, 87, 0.12);
  padding: 4px 10px;
  border-radius: 999px;
}
.fd-meaning {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #ece2d8;
  font-size: 13.5px;
  color: #6b5a4d;
  line-height: 1.6;
}

.flower-switch-enter-active,
.flower-switch-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.flower-switch-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.flower-switch-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.section-title {
  margin: 22px 2px 12px;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #7a6a5c;
}

/* 参考图小标签 */
.ref-chips {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.ref-chip {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  overflow: hidden;
  border: 1.5px solid #ddd4c8;
  box-shadow: 0 4px 12px rgba(90, 60, 40, 0.1);
  transition: transform 0.18s ease;
  padding: 0;
}
.ref-chip:active {
  transform: scale(0.94);
}
.ref-chip-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

/* 参考图大图弹窗 */
.ref-modal {
  position: absolute;
  inset: 0;
  z-index: 80;
  background: rgba(20, 16, 14, 0.88);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 30px;
}
.ref-modal-img {
  max-width: 100%;
  max-height: 100%;
  border-radius: 16px;
  object-fit: contain;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}
.ref-modal-close {
  position: absolute;
  top: calc(var(--safe-top) + 14px);
  right: 16px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.16);
  display: flex;
  align-items: center;
  justify-content: center;
}
.ref-fade-enter-active,
.ref-fade-leave-active {
  transition: opacity 0.2s ease;
}
.ref-fade-enter-from,
.ref-fade-leave-to {
  opacity: 0;
}

/* 花材清单 */
.flower-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  background: #fff;
  border: 1.5px solid transparent;
  border-radius: 16px;
  padding: 13px 14px;
  margin-bottom: 10px;
  box-shadow: 0 4px 14px rgba(90, 60, 40, 0.06);
  text-align: left;
}
.flower-row.active {
  border-color: var(--brand);
  background: #f0f5f1;
}
.fr-index {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: rgba(61, 107, 87, 0.12);
  color: var(--brand-deep);
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.fr-index.foliage {
  background: rgba(67, 170, 139, 0.14);
  color: #2f8f6f;
}
.fr-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.fr-name {
  font-size: 15px;
  font-weight: 700;
}
.fr-name em {
  font-style: normal;
  font-size: 11px;
  font-weight: 500;
  color: #a8988a;
  margin-left: 6px;
}
.fr-meaning {
  font-size: 12.5px;
  color: #9a8a7c;
}

.bottom-cta {
  flex-shrink: 0;
  padding: 12px 18px calc(var(--safe-bottom) + 16px);
  background: linear-gradient(180deg, rgba(250, 246, 241, 0), var(--paper) 30%);
}

.footer-actions {
  display: flex;
  gap: 12px;
}

.footer-actions .ghost-btn {
  flex: 1;
  border: 1.5px solid rgba(45, 74, 62, 0.24);
  color: var(--brand-deep);
  background: #fff;
}

.footer-actions .primary-btn {
  flex: 1.3;
}
</style>
