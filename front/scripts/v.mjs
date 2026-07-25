import { chromium } from 'playwright-core'
const browser = await chromium.launch({
  executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  headless: true, args: ['--autoplay-policy=no-user-gesture-required']
})
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true })
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
await page.waitForTimeout(3000)
await page.screenshot({ path: 'shots/f-feed.png' })
await page.locator('.wwsh-entry').click()
await page.waitForTimeout(900)
await page.screenshot({ path: 'shots/f-source.png' })
await browser.close()
console.log('done')
