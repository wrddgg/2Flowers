<template>
  <div class="bouquet-page">
    <header class="topbar">
      <button class="back-btn" @click="goTo('analysis')" aria-label="返回">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#1a1a1a" stroke-width="2.2" stroke-linecap="round">
          <path d="M15 5l-7 7 7 7" />
        </svg>
      </button>
      <span class="topbar-title">你的专属花束</span>
      <button class="capsule-close light" @click="goTo('feed')" aria-label="退出">
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
          <!-- 按归一化坐标渲染标签 -->
          <button
            v-for="(f, i) in currentResult.flowers"
            :key="f.name"
            class="flower-tag"
            :class="{ active: i === activeIndex, foliage: f.category === 'foliage' }"
            :style="tagStyle(f)"
            @click="selectFlower(i)"
          >
            <span class="tag-dot"></span>
            <span class="tag-name">{{ f.name }}</span>
          </button>
        </div>
      </div>

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

      <!-- 参考图片（后端生成时使用的参考链接，灰色小框） -->
      <section class="ref-section" v-if="currentResult.reference_used?.length">
        <p class="section-title">生成参考</p>
        <div class="ref-list">
          <div v-for="ref in currentResult.reference_used" :key="ref.reference_id" class="ref-box">
            <img :src="ref.cover_url" class="ref-thumb" alt="" />
            <div class="ref-copy">
              <span class="ref-title">{{ ref.title }}</span>
              <span class="ref-url">{{ ref.reason || shortUrl(ref.cover_url) }}</span>
            </div>
          </div>
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
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { store, goTo } from '../store'
import BouquetSvg from '../components/BouquetSvg.vue'

const bouquetResults = computed(() => store.bouquet?.results || [])
const selectedIndex = computed(() => store.selectedBouquetIndex || 0)
const currentResult = computed(() => bouquetResults.value[selectedIndex.value] || null)
const displayImage = computed(() => store.editedBouquetImage || currentResult.value?.bouquet_image || '')
const activeIndex = ref(0)
const active = computed(() => currentResult.value?.flowers[activeIndex.value])

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

/* 坐标标签 */
.flower-tag {
  position: absolute;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 11px 5px 7px;
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
}
.flower-tag.foliage .tag-dot {
  background: #43aa8b;
  box-shadow: 0 0 0 3px rgba(67, 170, 139, 0.25);
}
.flower-tag.active {
  background: var(--brand-deep);
  color: #fff;
  transform: translate(-50%, -50%) scale(1.12);
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

/* 参考图灰色小框 */
.ref-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ref-box {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #ece7e0;
  border: 1px solid #ddd4c8;
  border-radius: 12px;
  padding: 10px 14px;
}
.ref-thumb {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  object-fit: cover;
}
.ref-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.ref-title {
  font-size: 13px;
  font-weight: 700;
  color: #625346;
}
.ref-url {
  font-size: 12px;
  color: #8a7d70;
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
