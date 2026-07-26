<template>
  <div class="remake-plan-page">
    <div class="topbar">
      <button class="back-btn" @click="goTo('card')" aria-label="返回">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M15 18l-6-6 6-6" />
        </svg>
      </button>
      <span class="topbar-title">选择复刻方案</span>
      <button class="capsule-close light" @click="exitToFeed" aria-label="退出">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round">
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>
    </div>

    <div class="content">
      <p class="page-title">想用哪种方式复刻这束花？</p>

      <div class="option-list">
        <button
          v-for="opt in options"
          :key="opt.type"
          class="option-item"
          :class="{ active: selectedType === opt.type }"
          @click="selectedType = opt.type"
        >
          <span class="opt-radio"></span>
          <span class="opt-label">{{ opt.label }}</span>
        </button>
      </div>

      <button class="primary-btn view-btn" :disabled="!selectedType" @click="viewEffect">
        看看效果
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { store, goTo, exitToFeed } from '../store'

const options = [
  { type: 'perfect', label: '完美复刻版' },
  { type: 'ambience', label: '氛围复刻版' },
  { type: 'lightweight', label: '轻量复刻版' }
]
const selectedType = ref('perfect')

function viewEffect() {
  store.remakeOptionType = selectedType.value
  goTo('remake-result')
}
</script>

<style scoped>
.remake-plan-page {
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
  padding: 24px 22px calc(var(--safe-bottom) + 24px);
  display: flex;
  flex-direction: column;
}
.page-title {
  font-size: 18px;
  font-weight: 700;
  color: #3a2f28;
  letter-spacing: 1px;
  margin-bottom: 24px;
}
.option-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.option-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.8);
  border: 1.5px solid transparent;
  transition: all 0.18s ease;
}
.option-item.active {
  border-color: var(--brand-deep);
  background: rgba(61, 107, 87, 0.08);
}
.opt-radio {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 1.5px solid #c4b6a4;
  flex-shrink: 0;
  position: relative;
  transition: border-color 0.18s ease;
}
.option-item.active .opt-radio { border-color: var(--brand-deep); }
.option-item.active .opt-radio::after {
  content: '';
  position: absolute;
  inset: 3.5px;
  border-radius: 50%;
  background: var(--brand-deep);
}
.opt-label {
  font-size: 15px;
  font-weight: 600;
  color: #3a2f28;
  letter-spacing: 0.5px;
}
.view-btn {
  margin-top: auto;
  width: 100%;
  padding: 16px;
  border-radius: 999px;
  background: var(--brand-deep);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 2px;
  box-shadow: 0 10px 24px rgba(61, 107, 87, 0.3);
}
.view-btn:disabled {
  opacity: 0.5;
  box-shadow: none;
}
</style>
