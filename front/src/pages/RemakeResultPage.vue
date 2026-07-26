<template>
  <div class="remake-result-page">
    <div class="topbar">
      <button class="back-btn" @click="goTo('remake-plan')" aria-label="返回">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M15 18l-6-6 6-6" />
        </svg>
      </button>
      <span class="topbar-title">复刻效果</span>
      <button class="capsule-close light" @click="exitToFeed" aria-label="退出">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round">
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>
    </div>

    <div class="content">
      <!-- 生成中 -->
      <div v-if="loading" class="loading-box">
        <span class="spinner"></span>
        <p class="loading-text">正在生成复刻概念图…</p>
      </div>

      <!-- 生成完成 -->
      <template v-else>
        <p class="option-label">{{ optionLabel }}</p>
        <div class="preview-box">
          <img v-if="previewImage" :src="previewImage" class="preview-img" alt="复刻概念图" />
          <div v-else class="preview-fallback">
            <p>概念图生成失败，请重试</p>
          </div>
        </div>

        <div class="actions">
          <button class="ghost-btn" @click="saveCurrent">保存当前花束</button>
          <button class="primary-btn" @click="goTutorial">教我怎么复刻</button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { store, goTo, exitToFeed } from '../store'
import { remakePreview } from '../api'

const loading = ref(true)
const previewImage = ref('')

const OPTION_LABELS = {
  perfect: '完美复刻版',
  ambience: '氛围复刻版',
  lightweight: '轻量复刻版'
}
const optionLabel = computed(() => OPTION_LABELS[store.remakeOptionType] || '复刻方案')

const b = computed(() => store.bouquet?.results?.[store.selectedBouquetIndex] || null)

async function generate() {
  loading.value = true
  try {
    // 完美复刻版：直接用原花束图，不重新生成
    if (store.remakeOptionType === 'perfect') {
      previewImage.value = b.value?.bouquet_image || ''
      store.remakePreviewImage = previewImage.value
      store.remakePlan = null
      store.isRemakeCard = true
      loading.value = false
      return
    }
    // 氛围/轻量复刻版：调 remake-preview 图生图
    const preview = await remakePreview({
      resultId: b.value?.result_id,
      mode: store.analysis?.mode_result?.detected_mode || 'scene',
      optionType: store.remakeOptionType || 'ambience',
      voiceContext: store.voiceText || ''
    })
    if (preview?.preview_image_url) {
      previewImage.value = preview.preview_image_url
      store.remakePreviewImage = preview.preview_image_url
      store.remakePlan = preview.plan || null
      store.remakeResult = preview
      store.isRemakeCard = true // 标记为复刻花束卡
    }
  } catch (error) {
    console.warn('复刻概念图生成失败', error)
  } finally {
    loading.value = false
  }
}

function saveCurrent() {
  alert('当前花束已保存（演示）')
}

function goTutorial() {
  goTo('tutorial')
}

onMounted(generate)
</script>

<style scoped>
.remake-result-page {
  min-height: 100%;
  background: #f6f2ec;
  display: flex;
  flex-direction: column;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: calc(var(--safe-top) + 10px) 16px 10px;
}
.back-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #4a3b32;
}
.back-btn svg { width: 18px; height: 18px; }
.topbar-title {
  font-size: 15px;
  font-weight: 700;
  color: #3a2f28;
  letter-spacing: 1px;
}
.capsule-close {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #4a3b32;
}
.content {
  flex: 1;
  padding: 20px 22px calc(var(--safe-bottom) + 24px);
  display: flex;
  flex-direction: column;
}
.loading-box {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 18px;
}
.spinner {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 3.5px solid rgba(61, 107, 87, 0.18);
  border-top-color: var(--brand-deep);
  animation: spin 0.9s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loading-text {
  font-size: 14px;
  color: #7d6d5f;
  letter-spacing: 1px;
}
.option-label {
  font-size: 16px;
  font-weight: 700;
  color: var(--brand-deep);
  letter-spacing: 1px;
  margin-bottom: 14px;
}
.preview-box {
  border-radius: 20px;
  overflow: hidden;
  background: #ece7e0;
  box-shadow: 0 12px 32px rgba(90, 60, 40, 0.12);
}
.preview-img {
  width: 100%;
  display: block;
  object-fit: cover;
}
.preview-fallback {
  padding: 60px 20px;
  text-align: center;
  color: #8a7d70;
  font-size: 14px;
}
.actions {
  margin-top: auto;
  display: flex;
  gap: 12px;
  padding-top: 20px;
}
.ghost-btn, .primary-btn {
  flex: 1;
  padding: 15px;
  border-radius: 999px;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 1px;
}
.ghost-btn {
  background: rgba(255, 255, 255, 0.8);
  border: 1.5px solid #d8cfc2;
  color: #5a4a3d;
}
.primary-btn {
  background: var(--brand-deep);
  color: #fff;
  box-shadow: 0 10px 24px rgba(61, 107, 87, 0.3);
}
</style>
