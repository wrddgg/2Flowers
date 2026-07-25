const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

async function requestJson(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    },
    ...options
  })

  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(data.detail || data.error || '请求失败，请稍后再试。')
  }
  return data
}

async function requestWrapped(path, options = {}) {
  const data = await requestJson(path, options)
  if (data.code !== 0) {
    throw new Error(data.message || '请求失败，请稍后再试。')
  }
  return data.data
}

async function getImageMeta(imageDataUrl) {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => {
      resolve({
        width: image.naturalWidth || 1080,
        height: image.naturalHeight || 1440
      })
    }
    image.onerror = () => reject(new Error('图片读取失败，请换一张图片。'))
    image.src = imageDataUrl
  })
}

function stemFromFileName(fileName = '') {
  const cleaned = String(fileName).split(/[\\/]/).pop() || ''
  return cleaned.replace(/\.[^.]+$/, '') || 'upload_unknown'
}

function modeLabel(mode) {
  return (
    {
      scene: '场景转译',
      flower: '花束精修',
      life: '关系送礼'
    }[mode] || '灵感转译'
  )
}

function deriveTitle(raw) {
  const recommended = raw.interpretation_options?.find(
    (item) => item.option_id === raw.recommended_interpretation_id
  )
  return (
    recommended?.label ||
    raw.semantic_result?.subject_tags?.[0] ||
    raw.semantic_result?.semantic_summary ||
    '未命名画面'
  )
}

function toAnalysisView(raw) {
  return {
    ...raw,
    title: deriveTitle(raw),
    style: raw.semantic_result?.visual_tags?.join(' · ') || modeLabel(raw.mode_result?.detected_mode),
    palette: (raw.semantic_result?.color_swatches || []).map((s) => s.hex).filter(Boolean),
    mood: raw.semantic_result?.emotion_tags?.join('、') || '待识别',
    content: raw.semantic_result?.semantic_summary || '',
    scene: {
      person: raw.detected_elements?.some((item) => ['person', 'portrait'].includes(item.element_type)),
      place: raw.semantic_result?.scene_tags?.[0] || null,
      architecture: null,
      time: raw.semantic_result?.scene_tags?.[1] || null
    },
    segments: (raw.detected_elements || []).map((item, index) => ({
      label: item.element_type,
      bbox: [0.06, 0.1 + index * 0.12, 0.94, 0.18 + index * 0.12]
    }))
  }
}

function normalizeFlowerCategory(flower) {
  const joined = `${flower.type || ''}${flower.role || ''}${flower.name || ''}`
  return /叶|掌|尤加利/.test(joined) ? 'foliage' : 'flower'
}

function normalizeFlowers(flowers = []) {
  const defaultPoints = [
    [0.5, 0.28],
    [0.34, 0.46],
    [0.68, 0.44],
    [0.44, 0.63],
    [0.62, 0.66]
  ]

  return flowers.map((flower, index) => ({
    ...flower,
    name: flower.name,
    category: normalizeFlowerCategory(flower),
    role: flower.type || '花材',
    function: flower.role || '承接整体气质',
    point: defaultPoints[index] || [0.5, 0.5],
    confidence: Math.max(0.72, 0.94 - index * 0.05)
  }))
}

function normalizeBouquetResult(result, index) {
  return {
    ...result,
    bouquet_image: result.image_url,
    variant_title: result.generation_focus || `方案 ${index + 1}`,
    reference_images: (result.reference_used || []).map((item) => item.cover_url).filter(Boolean),
    flowers: normalizeFlowers(result.flowers || [])
  }
}

export async function analyzeImage({ imageDataUrl, fileName = '', voiceText = '' }) {
  const meta = await getImageMeta(imageDataUrl)
  const raw = await requestJson('/api/input/analyze', {
    method: 'POST',
    body: JSON.stringify({
      content_id: stemFromFileName(fileName),
      image_url: imageDataUrl,
      selection_box: {
        x: 0,
        y: 0,
        width: meta.width,
        height: meta.height
      },
      voice_text: voiceText || '把这个画面变成花'
    })
  })

  return {
    ...toAnalysisView(raw),
    source_meta: meta
  }
}

export async function searchReferences({ analysis, selectedInterpretationId }) {
  const selected =
    analysis?.interpretation_options?.find((item) => item.option_id === selectedInterpretationId) ||
    analysis?.interpretation_options?.find((item) => item.option_id === analysis?.recommended_interpretation_id) ||
    null
  const semantic = selected?.semantic_result || analysis?.semantic_result
  const mode = selected?.recommended_mode || analysis?.mode_result?.detected_mode || semantic?.mode || 'scene'
  const semanticTags = [
    ...(semantic?.scene_tags || []),
    ...(semantic?.emotion_tags || []),
    ...(semantic?.visual_tags || []),
    ...(semantic?.relation_tags || [])
  ]

  const raw = await requestJson('/api/reference/search', {
    method: 'POST',
    body: JSON.stringify({
      mode,
      semantic_tags: semanticTags,
      semantic_result: semantic,
      limit: 3
    })
  })
  return raw.references || []
}

export async function generateBouquet({ analysis, selectedInterpretationId, references = [] }) {
  const selected =
    analysis?.interpretation_options?.find((item) => item.option_id === selectedInterpretationId) ||
    analysis?.interpretation_options?.find((item) => item.option_id === analysis?.recommended_interpretation_id) ||
    null
  const semantic = selected?.semantic_result || analysis?.semantic_result
  const mode = selected?.recommended_mode || analysis?.mode_result?.detected_mode || semantic?.mode || 'scene'

  const raw = await requestJson('/api/bouquet/generate', {
    method: 'POST',
    body: JSON.stringify({
      mode,
      semantic_result: semantic,
      reference_strategy: references.length ? 'light' : 'none',
      selected_reference_ids: references.map((item) => item.reference_id),
      selected_interpretation_id: selected?.option_id || analysis?.recommended_interpretation_id || null,
      selected_interpretation_label: selected?.label || null,
      generation_goals: selected?.alignment_axes || []
    })
  })

  return {
    ...raw,
    results: (raw.results || []).map(normalizeBouquetResult)
  }
}

export async function buildEmotion({ resultId, mode, voiceContext = '' }) {
  return requestJson('/api/emotion/build', {
    method: 'POST',
    body: JSON.stringify({
      result_id: resultId,
      mode,
      voice_context: voiceContext
    })
  })
}

export async function editImage({ imageDataUrl, prompt, boxes }) {
  return requestJson('/api/image/edit', {
    method: 'POST',
    body: JSON.stringify({
      imageDataUrl,
      prompt,
      boxes
    })
  })
}

export async function generateTutorial({ bouquetImage, flowers, withImages = true }) {
  return requestWrapped('/api/generate-tutorial', {
    method: 'POST',
    body: JSON.stringify({
      bouquet_image: bouquetImage,
      flowers,
      with_images: withImages
    })
  })
}

export async function pollTutorialStatus(taskId) {
  return requestWrapped(`/api/tutorial-status?task_id=${encodeURIComponent(taskId)}`)
}

export async function generateShareCard({ before, after, title = '' }) {
  return requestWrapped('/api/generate-card', {
    method: 'POST',
    body: JSON.stringify({
      before,
      after,
      title
    })
  })
}
