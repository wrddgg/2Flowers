/**
 * 用 canvas 合成"原画面 vs 我的作品"对比图
 * 严格上下均分（各 50%），cover 填充
 * before: 原画面 dataURL（空则渐变占位）
 * after:  用户作品 dataURL
 * 返回 Promise<dataURL>
 */
export function composeCompareImage(before, after, title = '') {
  return new Promise((resolve) => {
    const W = 1080
    const H = 1920
    const half = H / 2 // 960，严格均分

    const canvas = document.createElement('canvas')
    canvas.width = W
    canvas.height = H
    const ctx = canvas.getContext('2d')

    const drawCover = (img, y) => {
      const scale = Math.max(W / img.width, half / img.height)
      const w = img.width * scale
      const h = img.height * scale
      ctx.save()
      ctx.beginPath()
      ctx.rect(0, y, W, half)
      ctx.clip()
      ctx.drawImage(img, (W - w) / 2, y + (half - h) / 2, w, h)
      ctx.restore()
    }

    const drawPlaceholder = (y, c1, c2) => {
      const g = ctx.createLinearGradient(0, y, 0, y + half)
      g.addColorStop(0, c1)
      g.addColorStop(1, c2)
      ctx.fillStyle = g
      ctx.fillRect(0, y, W, half)
    }

    const tag = (text, y) => {
      ctx.font = '600 34px sans-serif'
      const tw = ctx.measureText(text).width
      ctx.fillStyle = 'rgba(0,0,0,0.55)'
      roundRect(ctx, 32, y, tw + 48, 64, 32)
      ctx.fill()
      ctx.fillStyle = '#fff'
      ctx.fillText(text, 56, y + 44)
    }

    const finish = () => {
      // 中间白色分割线
      ctx.fillStyle = '#fff'
      ctx.fillRect(0, half - 4, W, 8)
      tag('原画面', 40)
      tag('我的作品', half + 40)
      // 底部水印
      if (title) {
        ctx.font = '500 32px sans-serif'
        const wm = `万物生花 · ${title}`
        const wt = ctx.measureText(wm).width
        ctx.fillStyle = 'rgba(0,0,0,0.45)'
        roundRect(ctx, (W - wt) / 2 - 28, H - 110, wt + 56, 66, 33)
        ctx.fill()
        ctx.fillStyle = '#fff'
        ctx.fillText(wm, (W - wt) / 2, H - 66)
      }
      resolve(canvas.toDataURL('image/jpeg', 0.9))
    }

    const loadImg = (src) =>
      new Promise((res) => {
        if (!src) return res(null)
        const img = new Image()
        img.onload = () => res(img)
        img.onerror = () => res(null)
        img.src = src
      })

    Promise.all([loadImg(before), loadImg(after)]).then(([bImg, aImg]) => {
      if (bImg) drawCover(bImg, 0)
      else drawPlaceholder(0, '#2b1055', '#e8a87c')
      if (aImg) drawCover(aImg, half)
      else drawPlaceholder(half, '#134e5e', '#f7dc6f')
      finish()
    })
  })
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
}
