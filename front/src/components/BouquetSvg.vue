<template>
  <!-- 手绘风花束 SVG，viewBox 1000x1000，坐标与 mock labels 归一化坐标对应 -->
  <svg viewBox="0 0 1000 1000" xmlns="http://www.w3.org/2000/svg" class="bouquet-svg">
    <defs>
      <radialGradient id="peonyG" cx="50%" cy="45%" r="60%">
        <stop offset="0%" stop-color="#ffb08a" />
        <stop offset="55%" stop-color="#ff7a59" />
        <stop offset="100%" stop-color="#e85d3d" />
      </radialGradient>
      <radialGradient id="peonyInner" cx="50%" cy="50%" r="55%">
        <stop offset="0%" stop-color="#ffd9a0" />
        <stop offset="100%" stop-color="#ff9e6d" />
      </radialGradient>
      <radialGradient id="violetG" cx="50%" cy="42%" r="60%">
        <stop offset="0%" stop-color="#d9c2f0" />
        <stop offset="100%" stop-color="#9b6fc9" />
      </radialGradient>
      <radialGradient id="lisiG" cx="50%" cy="45%" r="60%">
        <stop offset="0%" stop-color="#fff4e0" />
        <stop offset="100%" stop-color="#f2c99b" />
      </radialGradient>
      <linearGradient id="wrapG" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#f5ede2" />
        <stop offset="100%" stop-color="#e3d3bd" />
      </linearGradient>
    </defs>

    <!-- 背景 -->
    <rect width="1000" height="1000" fill="#efe9e1" />
    <rect width="1000" height="1000" fill="url(#bgV)" opacity="0.35" />
    <radialGradient id="bgV" cx="50%" cy="30%" r="80%">
      <stop offset="0%" stop-color="#ffffff" />
      <stop offset="100%" stop-color="#e2d8cc" />
    </radialGradient>

    <!-- 花茎 -->
    <g stroke="#5e8f6a" stroke-width="9" fill="none" stroke-linecap="round">
      <path d="M500 880 C 495 700, 498 560, 500 420" />
      <path d="M500 880 C 560 720, 660 600, 720 470" />
      <path d="M500 880 C 440 720, 340 620, 300 490" />
      <path d="M500 880 C 530 740, 570 650, 585 580" />
      <path d="M500 880 C 460 760, 410 680, 380 600" />
    </g>

    <!-- 尤加利叶 (point ~ [0.38, 0.58]) -->
    <g fill="#8fb8a3" opacity="0.95">
      <ellipse cx="330" cy="520" rx="34" ry="46" transform="rotate(-24 330 520)" />
      <ellipse cx="410" cy="560" rx="30" ry="42" transform="rotate(12 410 560)" />
      <ellipse cx="350" cy="630" rx="32" ry="44" transform="rotate(-10 350 630)" />
      <ellipse cx="440" cy="660" rx="26" ry="38" transform="rotate(20 440 660)" />
      <ellipse cx="290" cy="600" rx="26" ry="36" transform="rotate(-32 290 600)" />
    </g>
    <g fill="#7aa78f">
      <ellipse cx="620" cy="640" rx="28" ry="40" transform="rotate(18 620 640)" />
      <ellipse cx="670" cy="560" rx="24" ry="34" transform="rotate(30 670 560)" />
    </g>

    <!-- 紫罗兰 (point ~ [0.30, 0.44]) -->
    <g>
      <g transform="translate(300 440)">
        <ellipse rx="26" ry="40" cy="-22" fill="url(#violetG)" />
        <ellipse rx="26" ry="40" cy="-22" fill="url(#violetG)" transform="rotate(72)" />
        <ellipse rx="26" ry="40" cy="-22" fill="url(#violetG)" transform="rotate(144)" />
        <ellipse rx="26" ry="40" cy="-22" fill="url(#violetG)" transform="rotate(216)" />
        <ellipse rx="26" ry="40" cy="-22" fill="url(#violetG)" transform="rotate(288)" />
        <circle r="12" fill="#f4e285" />
      </g>
      <g transform="translate(240 520) scale(.72)">
        <ellipse rx="26" ry="40" cy="-22" fill="url(#violetG)" />
        <ellipse rx="26" ry="40" cy="-22" fill="url(#violetG)" transform="rotate(90)" />
        <ellipse rx="26" ry="40" cy="-22" fill="url(#violetG)" transform="rotate(180)" />
        <ellipse rx="26" ry="40" cy="-22" fill="url(#violetG)" transform="rotate(270)" />
        <circle r="12" fill="#f4e285" />
      </g>
    </g>

    <!-- 小雏菊 (point ~ [0.72, 0.42]) -->
    <g>
      <g transform="translate(720 420)">
        <g fill="#ffffff">
          <ellipse rx="14" ry="34" cy="-26" />
          <ellipse rx="14" ry="34" cy="-26" transform="rotate(45)" />
          <ellipse rx="14" ry="34" cy="-26" transform="rotate(90)" />
          <ellipse rx="14" ry="34" cy="-26" transform="rotate(135)" />
          <ellipse rx="14" ry="34" cy="-26" transform="rotate(180)" />
          <ellipse rx="14" ry="34" cy="-26" transform="rotate(225)" />
          <ellipse rx="14" ry="34" cy="-26" transform="rotate(270)" />
          <ellipse rx="14" ry="34" cy="-26" transform="rotate(315)" />
        </g>
        <circle r="16" fill="#f7c948" />
      </g>
      <g transform="translate(790 480) scale(.7)">
        <g fill="#ffffff">
          <ellipse rx="14" ry="34" cy="-26" />
          <ellipse rx="14" ry="34" cy="-26" transform="rotate(60)" />
          <ellipse rx="14" ry="34" cy="-26" transform="rotate(120)" />
          <ellipse rx="14" ry="34" cy="-26" transform="rotate(180)" />
          <ellipse rx="14" ry="34" cy="-26" transform="rotate(240)" />
          <ellipse rx="14" ry="34" cy="-26" transform="rotate(300)" />
        </g>
        <circle r="16" fill="#f7c948" />
      </g>
    </g>

    <!-- 洋桔梗 (point ~ [0.58, 0.55]) -->
    <g transform="translate(580 550)">
      <ellipse rx="30" ry="42" cy="-18" fill="url(#lisiG)" transform="rotate(-18)" />
      <ellipse rx="30" ry="42" cy="-18" fill="url(#lisiG)" transform="rotate(50)" />
      <ellipse rx="30" ry="42" cy="-18" fill="url(#lisiG)" transform="rotate(130)" />
      <ellipse rx="30" ry="42" cy="-18" fill="url(#lisiG)" transform="rotate(210)" />
      <ellipse rx="30" ry="42" cy="-18" fill="url(#lisiG)" transform="rotate(300)" />
      <circle r="13" fill="#e8a87c" />
    </g>

    <!-- 主花：落日珊瑚芍药 (point ~ [0.50, 0.36]) -->
    <g transform="translate(500 360)">
      <g fill="url(#peonyG)">
        <ellipse rx="52" ry="78" cy="-40" />
        <ellipse rx="52" ry="78" cy="-40" transform="rotate(45)" />
        <ellipse rx="52" ry="78" cy="-40" transform="rotate(90)" />
        <ellipse rx="52" ry="78" cy="-40" transform="rotate(135)" />
        <ellipse rx="52" ry="78" cy="-40" transform="rotate(180)" />
        <ellipse rx="52" ry="78" cy="-40" transform="rotate(225)" />
        <ellipse rx="52" ry="78" cy="-40" transform="rotate(270)" />
        <ellipse rx="52" ry="78" cy="-40" transform="rotate(315)" />
      </g>
      <g fill="url(#peonyInner)" opacity="0.95">
        <ellipse rx="30" ry="46" cy="-22" transform="rotate(22)" />
        <ellipse rx="30" ry="46" cy="-22" transform="rotate(112)" />
        <ellipse rx="30" ry="46" cy="-22" transform="rotate(202)" />
        <ellipse rx="30" ry="46" cy="-22" transform="rotate(292)" />
      </g>
      <circle r="17" fill="#ffd166" />
      <circle r="7" fill="#e8833a" />
    </g>

    <!-- 包装纸 -->
    <path d="M500 1000 L 370 760 Q 500 700 630 760 Z" fill="url(#wrapG)" />
    <path d="M370 760 Q 500 700 630 760 L 645 800 Q 500 745 355 800 Z" fill="#d9c8ae" opacity="0.7" />
    <path d="M430 830 Q 500 800 570 830 L 560 870 Q 500 845 440 870 Z" fill="#e83e6b" opacity="0.85" />
  </svg>
</template>

<style scoped>
.bouquet-svg {
  width: 100%;
  height: 100%;
  display: block;
}
</style>
