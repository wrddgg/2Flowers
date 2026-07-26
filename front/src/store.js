import { reactive, watch } from 'vue'

const STORAGE_KEY = 'wwsh_progress'

// 需要持久化的字段
const PERSIST_KEYS = [
  'page', 'videoSnapshot', 'sourceImage', 'sourceMeta', 'voiceText',
  'analysis', 'selectedInterpretationId', 'references',
  'bouquet', 'selectedBouquetIndex', 'editedBouquetImage', 'emotion',
  'tutorial', 'workPhoto', 'shareCard',
  'remakePreviewImage', 'remakePlan', 'remakeOptionType', 'remakeResult',
  'isRemakeCard', 'resumePage',
  'tutorialPhase', 'tutorialStepIndex', 'compareImage'
]

// 从 localStorage 恢复进度
function loadPersisted() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    return JSON.parse(raw) || {}
  } catch {
    return {}
  }
}

/**
 * 全局共享状态（轻量 store，跨页面传递数据）
 * page: feed | source | analysis | bouquet | edit | card | tutorial
 */
const persisted = loadPersisted()

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
  shareCard: null,
  // 复刻预览图（remake-preview 重新生成的花束图）
  remakePreviewImage: '',
  remakePlan: null,
  // 复刻选中的方案类型（perfect/ambience/lightweight）
  remakeOptionType: '',
  // 复刻生图结果
  remakeResult: null,
  // 当前卡片是否为复刻花束卡（区分普通保存花束卡）
  isRemakeCard: false,
  // 教程页进度（用于页面重载后恢复到准确阶段）
  tutorialPhase: '',
  tutorialStepIndex: 0,
  compareImage: '',
  // 退出创作时记录所在页面，用于"继续上次创作"
  resumePage: ''
})

// 用持久化的值覆盖默认值（恢复进度）
for (const key of PERSIST_KEYS) {
  if (persisted[key] !== undefined) {
    store[key] = persisted[key]
  }
}

// 监听 store 变化，自动持久化到 localStorage（防抖）
let saveTimer = null
watch(
  () => PERSIST_KEYS.map((k) => store[k]),
  () => {
    clearTimeout(saveTimer)
    saveTimer = setTimeout(() => {
      try {
        const data = {}
        for (const k of PERSIST_KEYS) data[k] = store[k]
        localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
      } catch (e) {
        // localStorage 满或序列化失败时静默忽略
        console.warn('进度保存失败', e)
      }
    }, 300)
  },
  { deep: true }
)

const PAGE_ORDER = ['feed', 'source', 'analysis', 'bouquet', 'edit', 'card', 'remake-plan', 'remake-result', 'tutorial']

export function goTo(page) {
  const from = PAGE_ORDER.indexOf(store.page)
  const to = PAGE_ORDER.indexOf(page)
  store.direction = to >= from ? 'forward' : 'back'
  store.page = page
}

// 退出创作回刷视频页：记录当前页面，便于"继续上次创作"恢复
export function exitToFeed() {
  // 只在有创作进度时记录，避免无效恢复
  if (store.bouquet || store.analysis) {
    store.resumePage = store.page
  }
  goTo('feed')
}

// 继续上次创作：返回退出时的页面
export function resumeFlow() {
  if (store.resumePage) {
    goTo(store.resumePage)
  } else {
    goTo('source')
  }
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
  store.remakePreviewImage = ''
  store.remakePlan = null
  store.remakeOptionType = ''
  store.remakeResult = null
  store.isRemakeCard = false
  store.resumePage = ''
  store.tutorialPhase = ''
  store.tutorialStepIndex = 0
  store.compareImage = ''
  // 清除持久化进度
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {}
}
