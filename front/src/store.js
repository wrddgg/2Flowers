import { reactive } from 'vue'

/**
 * 全局共享状态（轻量 store，跨页面传递数据）
 * page: feed | source | analysis | bouquet | edit | card | tutorial
 */
export const store = reactive({
  page: 'feed',
  // 页面切换方向：forward(右进) / back(左回)，用于转场动画
  direction: 'forward',
  // 页1 -> 页2：视频暂停帧截图 dataURL
  videoSnapshot: '',
  // 用户选择的画面（拍摄/相册/视频截图），dataURL
  sourceImage: '',
  sourceMeta: null,
  voiceText: '',
  // 后端分析结果
  analysis: null,
  selectedInterpretationId: '',
  references: [],
  // 花束生成结果
  bouquet: null,
  selectedBouquetIndex: 0,
  editedBouquetImage: '',
  emotion: null,
  // 接口3：教程结果
  tutorial: null,
  // 用户拍摄的作品
  workPhoto: '',
  // 接口4：分享卡片
  shareCard: null
})

const PAGE_ORDER = ['feed', 'source', 'analysis', 'bouquet', 'edit', 'card', 'tutorial']

export function goTo(page) {
  const from = PAGE_ORDER.indexOf(store.page)
  const to = PAGE_ORDER.indexOf(page)
  store.direction = to >= from ? 'forward' : 'back'
  store.page = page
}

export function resetFlow() {
  store.direction = 'forward'
  store.page = 'feed'
  store.videoSnapshot = ''
  store.sourceImage = ''
  store.sourceMeta = null
  store.voiceText = ''
  store.analysis = null
  store.selectedInterpretationId = ''
  store.references = []
  store.bouquet = null
  store.selectedBouquetIndex = 0
  store.editedBouquetImage = ''
  store.emotion = null
  store.tutorial = null
  store.workPhoto = ''
  store.shareCard = null
}
