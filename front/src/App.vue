<template>
  <div class="page-stage">
    <transition :name="transitionName">
      <component :is="currentPage" :key="store.page" />
    </transition>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { store } from './store'
import FeedPage from './pages/FeedPage.vue'
import SourcePage from './pages/SourcePage.vue'
import AnalysisPage from './pages/AnalysisPage.vue'
import BouquetPage from './pages/BouquetPage.vue'
import EditPage from './pages/EditPage.vue'
import CardPage from './pages/CardPage.vue'
import RemakePlanPage from './pages/RemakePlanPage.vue'
import RemakeResultPage from './pages/RemakeResultPage.vue'
import TutorialPage from './pages/TutorialPage.vue'

const pages = {
  feed: FeedPage,
  source: SourcePage,
  analysis: AnalysisPage,
  bouquet: BouquetPage,
  edit: EditPage,
  card: CardPage,
  'remake-plan': RemakePlanPage,
  'remake-result': RemakeResultPage,
  tutorial: TutorialPage
}

const currentPage = computed(() => pages[store.page])
const transitionName = computed(() =>
  store.direction === 'forward' ? 'slide-forward' : 'slide-back'
)
</script>
