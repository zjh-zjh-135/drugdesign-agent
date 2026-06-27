import React, { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Atom, ArrowRight, Sparkles, Zap, Shield, Database } from 'lucide-react'

// ===================== 原子属性 =====================
const ATOM_COLORS = {
  C: '#5a5a5a',  // 碳 - 深灰
  H: '#e8e8e8',  // 氢 - 米白
  O: '#e74c3c',  // 氧 - 红
  N: '#3498db',  // 氮 - 蓝
  S: '#f1c40f',  // 硫 - 黄
}

const ATOM_RADIUS = {
  C: 10, H: 5, O: 9, N: 9, S: 12,
}

// ===================== 3D 数学工具 =====================
function rotate3D(x, y, z, rotX, rotY, rotZ = 0) {
  let cx = Math.cos(rotZ), sx = Math.sin(rotZ)
  let x1 = x * cx - y * sx
  let y1 = x * sx + y * cx
  let z1 = z
  let cy = Math.cos(rotY), sy = Math.sin(rotY)
  let x2 = x1 * cy - z1 * sy
  let z2 = x1 * sy + z1 * cy
  let y2 = y1
  let cx2 = Math.cos(rotX), sx2 = Math.sin(rotX)
  let y3 = y2 * cx2 - z2 * sx2
  let z3 = y2 * sx2 + z2 * cx2
  return { x: x2, y: y3, z: z3 }
}

function project(x, y, z, fov, centerX, centerY) {
  const scale = fov / (fov + z)
  return { x: x * scale + centerX, y: y * scale + centerY, scale }
}

// ===================== 分子模板（真 3D 坐标） =====================
const MOLECULE_TEMPLATES = [
  // 1. 水 —— 弯曲形
  {
    name: 'H₂O',
    atoms: [
      { element: 'O', x: 0, y: 0, z: 0 },
      { element: 'H', x: 0.96, y: 0, z: 0.6 },
      { element: 'H', x: -0.24, y: 0.93, z: -0.6 },
    ],
    bonds: [[0, 1], [0, 2]],
  },
  // 2. 氨 —— 三角锥
  {
    name: 'NH₃',
    atoms: [
      { element: 'N', x: 0, y: 0, z: 0.4 },
      { element: 'H', x: 1.01, y: 0, z: -0.2 },
      { element: 'H', x: -0.34, y: 0.95, z: -0.2 },
      { element: 'H', x: -0.34, y: -0.48, z: -0.2 },
    ],
    bonds: [[0, 1], [0, 2], [0, 3]],
  },
  // 3. 甲醇 —— 四面体碳 + OH
  {
    name: 'CH₃OH',
    atoms: [
      { element: 'C', x: 0, y: 0, z: 0 },
      { element: 'O', x: 0, y: 0, z: 1.43 },
      { element: 'H', x: 1.02, y: 0, z: -0.36 },
      { element: 'H', x: -0.51, y: 0.88, z: -0.36 },
      { element: 'H', x: -0.51, y: -0.88, z: -0.36 },
      { element: 'H', x: 0.96, y: 0, z: 1.97 },
    ],
    bonds: [[0, 1], [0, 2], [0, 3], [0, 4], [1, 5]],
  },
  // 4. 乙醇 —— 两个四面体碳 + OH
  {
    name: 'C₂H₅OH',
    atoms: [
      { element: 'C', x: 0, y: 0, z: 0 },
      { element: 'C', x: 1.54, y: 0, z: 0 },
      { element: 'O', x: 2.54, y: 0, z: 1.0 },
      { element: 'H', x: -0.36, y: 1.02, z: 0 },
      { element: 'H', x: -0.36, y: -0.51, z: 0.88 },
      { element: 'H', x: -0.36, y: -0.51, z: -0.88 },
      { element: 'H', x: 1.9, y: 1.02, z: 0 },
      { element: 'H', x: 1.9, y: -0.51, z: 0.88 },
      { element: 'H', x: 1.9, y: -0.51, z: -0.88 },
      { element: 'H', x: 2.54, y: 0, z: 1.97 },
    ],
    bonds: [[0, 1], [1, 2], [0, 3], [0, 4], [0, 5], [1, 6], [1, 7], [1, 8], [2, 9]],
  },
  // 5. 环己烷 —— 椅式构象（交替上下）
  {
    name: 'Cyclohexane',
    atoms: [
      // 6个环碳（交替上下）
      { element: 'C', x: 1.0, y: 0, z: 0.5 },
      { element: 'C', x: 0.5, y: 0.87, z: -0.5 },
      { element: 'C', x: -0.5, y: 0.87, z: 0.5 },
      { element: 'C', x: -1.0, y: 0, z: -0.5 },
      { element: 'C', x: -0.5, y: -0.87, z: 0.5 },
      { element: 'C', x: 0.5, y: -0.87, z: -0.5 },
      // 轴向H（上下）
      { element: 'H', x: 1.0, y: 0, z: 1.5 },
      { element: 'H', x: 0.5, y: 0.87, z: -1.5 },
      { element: 'H', x: -0.5, y: 0.87, z: 1.5 },
      { element: 'H', x: -1.0, y: 0, z: -1.5 },
      { element: 'H', x: -0.5, y: -0.87, z: 1.5 },
      { element: 'H', x: 0.5, y: -0.87, z: -1.5 },
      // 平伏H（向外）
      { element: 'H', x: 1.9, y: 0, z: 0.0 },
      { element: 'H', x: 0.95, y: 1.65, z: 0.0 },
      { element: 'H', x: -0.95, y: 1.65, z: 0.0 },
      { element: 'H', x: -1.9, y: 0, z: 0.0 },
      { element: 'H', x: -0.95, y: -1.65, z: 0.0 },
      { element: 'H', x: 0.95, y: -1.65, z: 0.0 },
    ],
    bonds: [[0,1],[1,2],[2,3],[3,4],[4,5],[5,0],[0,6],[1,7],[2,8],[3,9],[4,10],[5,11],[0,12],[1,13],[2,14],[3,15],[4,16],[5,17]],
  },
  // 6. 金刚烷 —— 钻石笼（非常立体）
  {
    name: 'Adamantane',
    atoms: [
      // 4个桥头碳（四面体顶点）
      { element: 'C', x: 0, y: 0, z: 1.5 },
      { element: 'C', x: 1.43, y: 0.82, z: -0.5 },
      { element: 'C', x: -1.43, y: 0.82, z: -0.5 },
      { element: 'C', x: 0, y: -1.63, z: -0.5 },
      // 6个桥碳
      { element: 'C', x: 0.72, y: 0.41, z: 0.5 },
      { element: 'C', x: -0.72, y: 0.41, z: 0.5 },
      { element: 'C', x: 0, y: -0.82, z: 0.5 },
      { element: 'C', x: 0.72, y: -0.41, z: -0.5 },
      { element: 'C', x: -0.72, y: -0.41, z: -0.5 },
      { element: 'C', x: 0, y: 0.82, z: -0.5 },
      // H（16个）
      { element: 'H', x: 0, y: 0, z: 2.6 },
      { element: 'H', x: 2.5, y: 1.44, z: -0.5 },
      { element: 'H', x: -2.5, y: 1.44, z: -0.5 },
      { element: 'H', x: 0, y: -2.85, z: -0.5 },
      { element: 'H', x: 1.35, y: 1.35, z: 0.5 },
      { element: 'H', x: -1.35, y: 1.35, z: 0.5 },
      { element: 'H', x: 0, y: -1.7, z: 0.5 },
      { element: 'H', x: 1.35, y: -1.35, z: -0.5 },
      { element: 'H', x: -1.35, y: -1.35, z: -0.5 },
      { element: 'H', x: 0, y: 1.7, z: -0.5 },
      { element: 'H', x: 1.35, y: -0.78, z: 0.5 },
      { element: 'H', x: -1.35, y: -0.78, z: 0.5 },
      { element: 'H', x: 0, y: 0.78, z: 0.5 },
      { element: 'H', x: 1.35, y: 0.78, z: -0.5 },
      { element: 'H', x: -1.35, y: 0.78, z: -0.5 },
      { element: 'H', x: 0, y: -1.7, z: -0.5 },
    ],
    bonds: [[0,4],[0,5],[0,6],[4,5],[4,6],[5,6],[1,4],[1,7],[1,8],[4,7],[4,8],[7,8],[2,5],[2,7],[2,9],[5,7],[5,9],[7,9],[3,6],[3,8],[3,9],[6,8],[6,9],[8,9],[0,10],[1,11],[2,12],[3,13],[4,14],[5,15],[6,16],[7,17],[8,18],[9,19],[4,20],[5,21],[6,22],[7,23],[8,24],[9,25]],
  },
  // 7. 甲苯 —— 苯环 + 甲基伸出
  {
    name: 'Toluene',
    atoms: [
      // 苯环（略微倾斜）
      { element: 'C', x: 1.4, y: 0, z: 0.2 },
      { element: 'C', x: 0.7, y: 1.21, z: -0.1 },
      { element: 'C', x: -0.7, y: 1.21, z: 0.15 },
      { element: 'C', x: -1.4, y: 0, z: -0.2 },
      { element: 'C', x: -0.7, y: -1.21, z: 0.1 },
      { element: 'C', x: 0.7, y: -1.21, z: -0.15 },
      // 环H
      { element: 'H', x: 2.47, y: 0, z: 0.2 },
      { element: 'H', x: 1.235, y: 2.14, z: -0.1 },
      { element: 'H', x: -1.235, y: 2.14, z: 0.15 },
      { element: 'H', x: -2.47, y: 0, z: -0.2 },
      { element: 'H', x: -1.235, y: -2.14, z: 0.1 },
      // 甲基（四面体，伸出环平面）
      { element: 'C', x: 0.7, y: -1.21, z: 1.5 },
      { element: 'H', x: 1.4, y: -1.21, z: 2.1 },
      { element: 'H', x: 0.3, y: -0.5, z: 1.9 },
      { element: 'H', x: 0.3, y: -1.9, z: 1.9 },
    ],
    bonds: [[0,1],[1,2],[2,3],[3,4],[4,5],[5,0],[0,6],[1,7],[2,8],[3,9],[4,10],[5,11],[11,12],[12,13],[12,14],[12,15]],
  },
  // 8. 吡啶 —— 杂环 + N 略微凸出
  {
    name: 'Pyridine',
    atoms: [
      { element: 'C', x: 1.4, y: 0, z: 0 },
      { element: 'C', x: 0.7, y: 1.21, z: 0.1 },
      { element: 'N', x: -0.7, y: 1.21, z: 0.2 },
      { element: 'C', x: -1.4, y: 0, z: 0.1 },
      { element: 'C', x: -0.7, y: -1.21, z: -0.1 },
      { element: 'C', x: 0.7, y: -1.21, z: -0.1 },
      { element: 'H', x: 2.47, y: 0, z: 0 },
      { element: 'H', x: 1.235, y: 2.14, z: 0.1 },
      { element: 'H', x: -2.47, y: 0, z: 0.1 },
      { element: 'H', x: -1.235, y: -2.14, z: -0.1 },
      { element: 'H', x: 1.235, y: -2.14, z: -0.1 },
    ],
    bonds: [[0,1],[1,2],[2,3],[3,4],[4,5],[5,0],[0,6],[1,7],[3,8],[4,9],[5,10]],
  },
  // 9. 咖啡因 —— 双环 + 3个甲基显著伸出
  {
    name: 'Caffeine',
    atoms: [
      // 嘧啶环
      { element: 'C', x: 0, y: 0, z: 0 },
      { element: 'N', x: 1.3, y: 0, z: 0.1 },
      { element: 'C', x: 1.95, y: 1.13, z: 0.2 },
      { element: 'N', x: 1.3, y: 2.26, z: 0.1 },
      { element: 'C', x: 0, y: 2.26, z: 0 },
      // 咪唑环
      { element: 'C', x: -0.65, y: 1.13, z: -0.1 },
      { element: 'N', x: -1.95, y: 1.13, z: -0.2 },
      { element: 'C', x: -1.95, y: -0.2, z: -0.1 },
      { element: 'N', x: -0.65, y: -0.85, z: 0 },
      // C=O（伸出一个平面）
      { element: 'O', x: 0.3, y: 3.3, z: 0.8 },
      // N1-甲基（向上）
      { element: 'C', x: 2.7, y: -0.8, z: 1.2 },
      { element: 'H', x: 3.4, y: -0.2, z: 1.8 },
      { element: 'H', x: 2.8, y: -1.4, z: 1.8 },
      { element: 'H', x: 3.2, y: -1.2, z: 0.7 },
      // N3-甲基（向下）
      { element: 'C', x: 2.7, y: 3.0, z: -1.2 },
      { element: 'H', x: 3.4, y: 2.4, z: -1.8 },
      { element: 'H', x: 2.8, y: 3.6, z: -1.8 },
      { element: 'H', x: 3.2, y: 2.8, z: -0.7 },
      // N7-甲基（向左上）
      { element: 'C', x: -2.8, y: -0.8, z: 1.0 },
      { element: 'H', x: -3.5, y: -0.2, z: 1.6 },
      { element: 'H', x: -2.9, y: -1.4, z: 1.6 },
      { element: 'H', x: -3.2, y: -1.2, z: 0.5 },
    ],
    bonds: [[0,1],[1,2],[2,3],[3,4],[4,5],[5,0],[5,6],[6,7],[7,8],[8,0],[4,9],[1,10],[10,11],[10,12],[10,13],[3,14],[14,15],[14,16],[14,17],[7,18],[18,19],[18,20],[18,21]],
  },
  // 10. 尼古丁 —— 吡啶 + 吡咯烷（褶皱）
  {
    name: 'Nicotine',
    atoms: [
      // 吡啶环（略微倾斜）
      { element: 'C', x: 1.4, y: 0, z: 0.1 },
      { element: 'C', x: 0.7, y: 1.21, z: -0.1 },
      { element: 'N', x: -0.7, y: 1.21, z: 0.1 },
      { element: 'C', x: -1.4, y: 0, z: -0.1 },
      { element: 'C', x: -0.7, y: -1.21, z: 0.1 },
      { element: 'C', x: 0.7, y: -1.21, z: -0.1 },
      // 吡啶H
      { element: 'H', x: 2.47, y: 0, z: 0.1 },
      { element: 'H', x: 1.235, y: 2.14, z: -0.1 },
      { element: 'H', x: -2.47, y: 0, z: -0.1 },
      { element: 'H', x: -1.235, y: -2.14, z: 0.1 },
      { element: 'H', x: 1.235, y: -2.14, z: -0.1 },
      // 吡咯烷连接（向上伸出）
      { element: 'C', x: -0.7, y: 2.5, z: 0.8 },
      { element: 'C', x: -2.1, y: 2.8, z: 0.3 },
      { element: 'N', x: -2.8, y: 1.6, z: -0.5 },
      { element: 'C', x: -1.8, y: 0.6, z: -0.3 },
      { element: 'C', x: -2.8, y: 3.8, z: 1.0 },
      // 吡咯烷H
      { element: 'H', x: -0.2, y: 3.2, z: 1.2 },
      { element: 'H', x: -2.1, y: 2.8, z: -0.7 },
      { element: 'H', x: -2.8, y: 0.5, z: -1.2 },
      { element: 'H', x: -1.5, y: -0.2, z: -0.8 },
      { element: 'H', x: -3.7, y: 3.8, z: 1.2 },
      { element: 'H', x: -2.5, y: 4.5, z: 1.2 },
      { element: 'H', x: -2.8, y: 3.8, z: 0.1 },
      // N-甲基
      { element: 'C', x: -3.8, y: 1.4, z: -1.2 },
      { element: 'H', x: -4.5, y: 1.9, z: -1.8 },
      { element: 'H', x: -3.9, y: 0.4, z: -1.4 },
      { element: 'H', x: -3.8, y: 1.4, z: -2.2 },
    ],
    bonds: [[0,1],[1,2],[2,3],[3,4],[4,5],[5,0],[1,11],[11,12],[12,13],[13,14],[14,2],[12,15],[11,16],[13,17],[14,18],[15,19],[15,20],[15,21],[13,22],[22,23],[22,24],[22,25]],
  },
  // 11. 多巴胺 —— 苯环 + 侧链 + 2个OH
  {
    name: 'Dopamine',
    atoms: [
      // 苯环
      { element: 'C', x: 0, y: 0, z: 0 },
      { element: 'C', x: 1.4, y: 0, z: 0.1 },
      { element: 'C', x: 2.1, y: 1.21, z: 0.2 },
      { element: 'C', x: 1.4, y: 2.42, z: 0.1 },
      { element: 'C', x: 0, y: 2.42, z: 0 },
      { element: 'C', x: -0.7, y: 1.21, z: -0.1 },
      // OH（伸出环平面）
      { element: 'O', x: -1.0, y: -0.8, z: 1.0 },
      { element: 'O', x: 2.1, y: 3.4, z: 1.0 },
      { element: 'H', x: -1.8, y: -0.6, z: 1.5 },
      { element: 'H', x: 2.8, y: 3.2, z: 1.5 },
      // 乙胺链（伸出平面）
      { element: 'C', x: -0.7, y: -1.21, z: -1.0 },
      { element: 'C', x: -1.4, y: -2.42, z: -1.5 },
      { element: 'N', x: -0.7, y: -3.63, z: -1.0 },
      // 苯环H
      { element: 'H', x: 2.87, y: 1.21, z: 0.3 },
      { element: 'H', x: -0.7, y: 3.42, z: 0.1 },
      // 链H
      { element: 'H', x: -2.47, y: -1.21, z: -1.2 },
      { element: 'H', x: -1.4, y: -1.21, z: -1.9 },
      { element: 'H', x: -2.47, y: -2.42, z: -1.7 },
      { element: 'H', x: -1.4, y: -2.42, z: -2.3 },
      { element: 'H', x: -0.7, y: -4.63, z: -1.5 },
      { element: 'H', x: -1.5, y: -3.63, z: -0.5 },
      { element: 'H', x: 0.1, y: -3.63, z: -0.5 },
    ],
    bonds: [[0,1],[1,2],[2,3],[3,4],[4,5],[5,0],[0,6],[6,8],[3,7],[7,9],[5,10],[10,11],[11,12],[2,13],[4,14],[10,15],[10,16],[11,17],[11,18],[12,19],[12,20],[12,21]],
  },
  // 12. 葡萄糖 —— 吡喃糖椅式（非常立体）
  {
    name: 'Glucose',
    atoms: [
      // 6元环（椅式）
      { element: 'C', x: 1.0, y: 0, z: 0.5 },
      { element: 'C', x: 0.5, y: 0.87, z: -0.5 },
      { element: 'C', x: -0.5, y: 0.87, z: 0.5 },
      { element: 'C', x: -1.0, y: 0, z: -0.5 },
      { element: 'C', x: -0.5, y: -0.87, z: 0.5 },
      { element: 'O', x: 0.5, y: -0.87, z: -0.5 },
      // C1-CH2OH（伸出）
      { element: 'C', x: 1.0, y: 0, z: 1.8 },
      { element: 'O', x: 1.0, y: 0, z: 2.8 },
      { element: 'H', x: 1.9, y: 0, z: 2.3 },
      { element: 'H', x: 0.1, y: 0, z: 2.3 },
      // C2-OH
      { element: 'O', x: 0.5, y: 1.87, z: -1.3 },
      { element: 'H', x: 0.5, y: 2.67, z: -1.3 },
      // C3-OH
      { element: 'O', x: -0.5, y: 1.87, z: 1.3 },
      { element: 'H', x: -0.5, y: 2.67, z: 1.3 },
      // C4-OH
      { element: 'O', x: -1.0, y: 0, z: -1.8 },
      { element: 'H', x: -1.0, y: 0, z: -2.7 },
      // C5-CH2OH
      { element: 'C', x: -0.5, y: -1.87, z: 1.5 },
      { element: 'O', x: -0.5, y: -2.87, z: 1.5 },
      { element: 'H', x: -1.4, y: -3.2, z: 1.5 },
      // 环H
      { element: 'H', x: 1.9, y: 0, z: 0.0 },
      { element: 'H', x: 0.95, y: 1.65, z: 0.0 },
      { element: 'H', x: -0.95, y: 1.65, z: 0.0 },
      { element: 'H', x: -1.9, y: 0, z: 0.0 },
      { element: 'H', x: -1.4, y: -1.87, z: 0.5 },
      { element: 'H', x: 1.4, y: 0, z: 1.5 },
    ],
    bonds: [[0,1],[1,2],[2,3],[3,4],[4,5],[5,0],[0,6],[6,7],[7,8],[7,9],[1,10],[10,11],[2,12],[12,13],[3,14],[14,15],[4,16],[16,17],[17,18],[0,19],[1,20],[2,21],[3,22],[4,23],[6,24]],
  },
  // 13. 苯丙氨酸 —— 苯环 + 手性碳 + 氨基 + 羧基
  {
    name: 'Phenylalanine',
    atoms: [
      // 苯环
      { element: 'C', x: 0, y: 0, z: 0 },
      { element: 'C', x: 1.4, y: 0, z: 0.1 },
      { element: 'C', x: 2.1, y: 1.21, z: 0.2 },
      { element: 'C', x: 1.4, y: 2.42, z: 0.1 },
      { element: 'C', x: 0, y: 2.42, z: 0 },
      { element: 'C', x: -0.7, y: 1.21, z: -0.1 },
      // CH2（伸出环）
      { element: 'C', x: -0.7, y: -1.21, z: 0.8 },
      // 手性α-CH（四面体）
      { element: 'C', x: -1.4, y: -2.42, z: -0.5 },
      // NH2
      { element: 'N', x: -2.8, y: -2.42, z: 0.0 },
      { element: 'H', x: -3.3, y: -1.6, z: -0.3 },
      { element: 'H', x: -3.3, y: -3.2, z: -0.3 },
      // COOH
      { element: 'C', x: -1.4, y: -3.73, z: -1.2 },
      { element: 'O', x: -0.3, y: -4.1, z: -1.5 },
      { element: 'O', x: -2.4, y: -4.5, z: -1.5 },
      { element: 'H', x: -2.8, y: -4.2, z: -2.2 },
      // H
      { element: 'H', x: 2.87, y: 1.21, z: 0.3 },
      { element: 'H', x: -0.7, y: 3.42, z: 0.1 },
      { element: 'H', x: -1.4, y: -1.21, z: 1.4 },
      { element: 'H', x: -0.7, y: -1.21, z: -0.2 },
      { element: 'H', x: -1.4, y: -2.42, z: -1.5 },
      { element: 'H', x: -2.8, y: -2.42, z: 0.8 },
    ],
    bonds: [[0,1],[1,2],[2,3],[3,4],[4,5],[5,0],[0,6],[6,7],[7,8],[8,9],[8,10],[7,11],[11,12],[11,13],[13,14],[2,15],[4,16],[6,17],[6,18],[7,19],[8,20]],
  },
  // 14. 阿司匹林 —— 苯环 + 酯基
  {
    name: 'Aspirin',
    atoms: [
      // 苯环
      { element: 'C', x: 0, y: 0, z: 0 },
      { element: 'C', x: 1.4, y: 0, z: 0.1 },
      { element: 'C', x: 2.1, y: 1.21, z: 0.2 },
      { element: 'C', x: 1.4, y: 2.42, z: 0.1 },
      { element: 'C', x: 0, y: 2.42, z: 0 },
      { element: 'C', x: -0.7, y: 1.21, z: -0.1 },
      // COOH（伸出）
      { element: 'C', x: -0.7, y: -1.21, z: 0.8 },
      { element: 'O', x: -0.7, y: -1.21, z: 2.0 },
      { element: 'O', x: -1.7, y: -1.21, z: 0.3 },
      { element: 'H', x: -2.4, y: -1.21, z: 0.8 },
      // OCOCH3（向上伸出）
      { element: 'O', x: 2.1, y: 3.4, z: 1.0 },
      { element: 'C', x: 3.3, y: 3.4, z: 1.5 },
      { element: 'O', x: 4.0, y: 3.4, z: 0.8 },
      { element: 'C', x: 3.3, y: 3.4, z: 2.8 },
      { element: 'H', x: 2.87, y: 1.21, z: 0.3 },
      { element: 'H', x: -0.7, y: 3.42, z: 0.1 },
      { element: 'H', x: 3.8, y: 3.4, z: 3.3 },
      { element: 'H', x: 2.8, y: 4.0, z: 2.8 },
      { element: 'H', x: 2.8, y: 2.8, z: 2.8 },
    ],
    bonds: [[0,1],[1,2],[2,3],[3,4],[4,5],[5,0],[0,6],[6,7],[6,8],[8,9],[3,10],[10,11],[11,12],[11,13],[2,14],[4,15],[13,16],[13,17],[13,18]],
  },
  // 15. 胆固醇骨架简化（甾环）
  {
    name: 'Steroid',
    atoms: [
      // 四个环骨架（简化示意）
      // A环
      { element: 'C', x: 0, y: 0, z: 0 },
      { element: 'C', x: 1.4, y: 0, z: 0.1 },
      { element: 'C', x: 2.1, y: 1.21, z: 0.2 },
      { element: 'C', x: 1.4, y: 2.42, z: 0.1 },
      { element: 'C', x: 0, y: 2.42, z: 0 },
      { element: 'C', x: -0.7, y: 1.21, z: -0.1 },
      // B环（连接在A环）
      { element: 'C', x: -0.7, y: -1.21, z: 0.8 },
      { element: 'C', x: -1.4, y: -2.42, z: 0.3 },
      { element: 'C', x: -0.7, y: -3.63, z: 0.8 },
      { element: 'C', x: 0.7, y: -3.63, z: 0.3 },
      // C环（连接在B环）
      { element: 'C', x: 1.4, y: -2.42, z: 0.8 },
      { element: 'C', x: 0.7, y: -1.21, z: 0.3 },
      // D环（五元环）
      { element: 'C', x: 2.1, y: -3.63, z: 0.8 },
      { element: 'C', x: 2.8, y: -2.42, z: 0.3 },
      { element: 'C', x: 2.1, y: -1.21, z: 0.8 },
      // 一些H和甲基示意
      { element: 'C', x: -0.7, y: 3.63, z: 0.5 },
      { element: 'C', x: 2.8, y: -0.6, z: 0.5 },
      { element: 'C', x: 3.5, y: -3.63, z: 0.5 },
      // H
      { element: 'H', x: 2.87, y: 1.21, z: 0.3 },
      { element: 'H', x: -0.7, y: 3.63, z: 1.5 },
      { element: 'H', x: 2.8, y: -0.6, z: 1.5 },
      { element: 'H', x: 3.5, y: -3.63, z: 1.5 },
    ],
    bonds: [[0,1],[1,2],[2,3],[3,4],[4,5],[5,0],[0,6],[6,7],[7,8],[8,9],[9,10],[10,11],[11,0],[8,13],[13,14],[14,15],[15,11],[4,16],[2,17],[13,18],[2,19],[16,20],[17,21],[18,22]],
  },
]

// ===================== 主组件 =====================
function HomePage() {
  const canvasRef = useRef(null)
  const animationRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const parent = canvas.parentElement
    let width = canvas.width = parent.offsetWidth
    let height = canvas.height = parent.offsetHeight

    const SCALE = 16

    // 初始化分子实例：15个大分子 + 6个水
    const instances = []
    const numMolecules = 21
    for (let i = 0; i < numMolecules; i++) {
      let template
      if (i < 15) {
        template = MOLECULE_TEMPLATES[i % MOLECULE_TEMPLATES.length]
      } else {
        // 后6个固定是水分子
        template = {
          name: 'H₂O',
          atoms: [
            { element: 'O', x: 0, y: 0, z: 0 },
            { element: 'H', x: 0.96, y: 0, z: 0.6 },
            { element: 'H', x: -0.24, y: 0.93, z: -0.6 },
          ],
          bonds: [[0, 1], [0, 2]],
        }
      }
      let maxDist = 0
      for (const a of template.atoms) {
        const d = Math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z)
        if (d > maxDist) maxDist = d
      }
      const hitRadius = maxDist * SCALE * 1.3

      instances.push({
        ...template,
        wx: Math.random() * width,
        wy: Math.random() * height,
        wz: (Math.random() - 0.5) * 120,
        vx: (Math.random() - 0.5) * 0.24,
        vy: (Math.random() - 0.5) * 0.16,
        rotX: Math.random() * Math.PI * 2,
        rotY: Math.random() * Math.PI * 2,
        rotZ: Math.random() * Math.PI * 2,
        rotSpeedX: 0.0016 + Math.random() * 0.0024,
        rotSpeedY: 0.0012 + Math.random() * 0.0032,
        rotSpeedZ: 0.0008 + Math.random() * 0.0016,
        scale: 1,
        targetScale: 1,
        hovered: false,
        dragging: false,
        hitRadius,
        // 加载动画：从无到有
        spawnScale: 0,
        spawnDelay: i * 0.04,
      })
    }

    const mouse = { x: -9999, y: -9999, down: false, lastX: 0, lastY: 0 }
    let draggedInstance = null

    // 鼠标轨迹拖尾
    const mouseTrail = []
    const TRAIL_LENGTH = 12

    const stars = []
    for (let i = 0; i < 100; i++) {
      stars.push({
        x: Math.random() * width,
        y: Math.random() * height,
        size: Math.random() * 1.2 + 0.3,
        opacity: Math.random() * 0.5 + 0.1,
        phase: Math.random() * Math.PI * 2,
      })
    }

    const getMousePos = (e) => {
      const rect = canvas.getBoundingClientRect()
      return { x: e.clientX - rect.left, y: e.clientY - rect.top }
    }

    const handleMouseMove = (e) => {
      const pos = getMousePos(e)
      mouse.x = pos.x
      mouse.y = pos.y

      if (draggedInstance) {
        const dx = mouse.x - mouse.lastX
        const dy = mouse.y - mouse.lastY
        draggedInstance.rotY += dx * 0.0064
        draggedInstance.rotX += dy * 0.0064
      } else {
        let closest = null
        let closestDist = Infinity
        for (const mol of instances) {
          const dx = mol.wx - mouse.x
          const dy = mol.wy - mouse.y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < mol.hitRadius && dist < closestDist) {
            closest = mol
            closestDist = dist
          }
        }
        for (const mol of instances) {
          mol.hovered = (mol === closest)
          mol.targetScale = mol.hovered ? 1.4 : 1.0
        }
        canvas.style.cursor = closest ? 'grab' : 'default'
      }
      mouse.lastX = mouse.x
      mouse.lastY = mouse.y

      // 更新鼠标拖尾
      mouseTrail.push({ x: mouse.x, y: mouse.y })
      if (mouseTrail.length > TRAIL_LENGTH) mouseTrail.shift()
    }

    const handleMouseDown = (e) => {
      mouse.down = true
      const pos = getMousePos(e)
      mouse.lastX = pos.x
      mouse.lastY = pos.y
      for (const mol of instances) {
        const dx = mol.wx - pos.x
        const dy = mol.wy - pos.y
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < mol.hitRadius * 1.2) {
          draggedInstance = mol
          mol.dragging = true
          canvas.style.cursor = 'grabbing'
          break
        }
      }
    }

    const handleMouseUp = () => {
      mouse.down = false
      if (draggedInstance) {
        draggedInstance.dragging = false
        draggedInstance = null
        canvas.style.cursor = 'default'
      }
    }

    const handleMouseLeave = () => {
      mouse.x = -9999
      mouse.y = -9999
      for (const mol of instances) {
        mol.hovered = false
        mol.targetScale = 1.0
      }
      if (draggedInstance) {
        draggedInstance.dragging = false
        draggedInstance = null
      }
      canvas.style.cursor = 'default'
    }

    canvas.addEventListener('mousemove', handleMouseMove)
    canvas.addEventListener('mousedown', handleMouseDown)
    canvas.addEventListener('mouseup', handleMouseUp)
    canvas.addEventListener('mouseleave', handleMouseLeave)

    const handleTouchStart = (e) => {
      e.preventDefault()
      const touch = e.touches[0]
      const rect = canvas.getBoundingClientRect()
      const tx = touch.clientX - rect.left
      const ty = touch.clientY - rect.top
      mouse.lastX = tx
      mouse.lastY = ty
      for (const mol of instances) {
        const dx = mol.wx - tx
        const dy = mol.wy - ty
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < mol.hitRadius * 1.2) {
          draggedInstance = mol
          mol.dragging = true
          break
        }
      }
    }
    const handleTouchMove = (e) => {
      e.preventDefault()
      const touch = e.touches[0]
      const rect = canvas.getBoundingClientRect()
      const tx = touch.clientX - rect.left
      const ty = touch.clientY - rect.top
      if (draggedInstance) {
        const dx = tx - mouse.lastX
        const dy = ty - mouse.lastY
        draggedInstance.rotY += dx * 0.0096
        draggedInstance.rotX += dy * 0.0096
      }
      mouse.lastX = tx
      mouse.lastY = ty
    }
    const handleTouchEnd = () => {
      if (draggedInstance) {
        draggedInstance.dragging = false
        draggedInstance = null
      }
    }

    canvas.addEventListener('touchstart', handleTouchStart, { passive: false })
    canvas.addEventListener('touchmove', handleTouchMove, { passive: false })
    canvas.addEventListener('touchend', handleTouchEnd)

    let time = 0

    function drawMolecule(mol, fov) {
      if (!mol.dragging) {
        mol.rotX += mol.rotSpeedX
        mol.rotY += mol.rotSpeedY
        mol.rotZ += mol.rotSpeedZ
      }

      mol.scale += (mol.targetScale - mol.scale) * 0.08
      const finalScale = mol.scale * mol.spawnScale

      const projected = mol.atoms.map((a) => {
        const rot = rotate3D(a.x * SCALE, a.y * SCALE, a.z * SCALE, mol.rotX, mol.rotY, mol.rotZ)
        const proj = project(rot.x, rot.y, rot.z + mol.wz, fov, mol.wx, mol.wy)
        return {
          ...proj,
          z: rot.z + mol.wz,
          r: ATOM_RADIUS[a.element] * proj.scale * finalScale,
          color: ATOM_COLORS[a.element],
          element: a.element,
        }
      })

      const bondData = mol.bonds.map(([i, j]) => {
        const pi = projected[i]
        const pj = projected[j]
        const avgZ = (pi.z + pj.z) / 2
        return { i, j, avgZ, pi, pj }
      })

      const renderItems = []
      for (const b of bondData) {
        renderItems.push({ type: 'bond', z: b.avgZ, data: b })
      }
      for (let idx = 0; idx < projected.length; idx++) {
        renderItems.push({ type: 'atom', z: projected[idx].z, data: projected[idx], idx })
      }
      renderItems.sort((a, b) => b.z - a.z)

      for (const item of renderItems) {
        if (item.type === 'bond') {
          const { pi, pj } = item.data
          const avgScale = (pi.scale + pj.scale) / 2 * finalScale
          const opacity = Math.max(0.15, Math.min(0.5, (item.z + 200) / 400))
          ctx.beginPath()
          ctx.moveTo(pi.x, pi.y)
          ctx.lineTo(pj.x, pj.y)
          ctx.strokeStyle = `rgba(180, 200, 220, ${opacity})`
          ctx.lineWidth = 2.5 * avgScale
          ctx.lineCap = 'round'
          ctx.stroke()
        } else {
          const p = item.data
          const opacity = Math.max(0.3, Math.min(1, (p.z + 200) / 400))
          const r = p.r

          if (mol.hovered || mol.dragging) {
            const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * 3.5)
            glow.addColorStop(0, p.color + '60')
            glow.addColorStop(0.5, p.color + '20')
            glow.addColorStop(1, p.color + '00')
            ctx.fillStyle = glow
            ctx.beginPath()
            ctx.arc(p.x, p.y, r * 3.5, 0, Math.PI * 2)
            ctx.fill()
          } else {
            const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * 2.5)
            glow.addColorStop(0, p.color + '25')
            glow.addColorStop(1, p.color + '00')
            ctx.fillStyle = glow
            ctx.beginPath()
            ctx.arc(p.x, p.y, r * 2.5, 0, Math.PI * 2)
            ctx.fill()
          }

          ctx.beginPath()
          ctx.arc(p.x, p.y, r, 0, Math.PI * 2)
          ctx.fillStyle = p.color
          ctx.fill()

          const hlR = r * 0.35
          ctx.beginPath()
          ctx.arc(p.x - r * 0.25, p.y - r * 0.25, hlR, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(255, 255, 255, ${opacity * 0.55})`
          ctx.fill()

          ctx.beginPath()
          ctx.arc(p.x - r * 0.15, p.y - r * 0.15, r * 0.12, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(255, 255, 255, ${opacity * 0.8})`
          ctx.fill()

          if (mol.hovered || mol.dragging) {
            ctx.font = `bold ${Math.max(8, Math.floor(r * 0.8))}px sans-serif`
            ctx.textAlign = 'center'
            ctx.textBaseline = 'middle'
            ctx.fillStyle = p.element === 'H' ? '#333' : '#fff'
            ctx.fillText(p.element, p.x, p.y + 1)
          }
        }
      }

      if (mol.hovered || mol.dragging) {
        ctx.font = 'bold 13px sans-serif'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'bottom'
        ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'
        ctx.fillText(mol.name, mol.wx, mol.wy - mol.hitRadius * finalScale * 0.6)
      }
    }

    function animate() {
      ctx.fillStyle = 'rgba(2, 4, 10, 0.12)'
      ctx.fillRect(0, 0, width, height)
      time += 0.016

      // 鼠标轨迹拖尾
      for (let i = 0; i < mouseTrail.length; i++) {
        const t = mouseTrail[i]
        const opacity = ((i + 1) / mouseTrail.length) * 0.18
        const radius = 1.5 + i * 0.25
        ctx.beginPath()
        ctx.arc(t.x, t.y, radius, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(255, 255, 255, ${opacity})`
        ctx.fill()
      }

      for (const s of stars) {
        const twinkle = 0.5 + 0.5 * Math.sin(s.phase + time * 0.8)
        ctx.beginPath()
        ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(255, 255, 255, ${s.opacity * twinkle})`
        ctx.fill()
      }

      for (const mol of instances) {
        // 加载动画：分子从无到有
        if (time > mol.spawnDelay) {
          const progress = (time - mol.spawnDelay) / 0.5
          mol.spawnScale = Math.min(1, progress)
        } else {
          mol.spawnScale = 0
        }

        if (!mol.dragging) {
          mol.wx += mol.vx
          mol.wy += mol.vy
          mol.vx += (Math.random() - 0.5) * 0.012
          mol.vy += (Math.random() - 0.5) * 0.012
          mol.vx *= 0.995
          mol.vy *= 0.995

          // 软斥力：避免分子扎堆
          for (const other of instances) {
            if (other === mol) continue
            const dx = mol.wx - other.wx
            const dy = mol.wy - other.wy
            const dist = Math.sqrt(dx * dx + dy * dy) || 1
            const minDist = (mol.hitRadius + other.hitRadius) * 0.8
            if (dist < minDist) {
              const force = 0.3 * (minDist - dist) / minDist
              mol.vx += (dx / dist) * force
              mol.vy += (dy / dist) * force
            }
          }

          const margin = mol.hitRadius * 2
          if (mol.wx > width + margin) mol.wx = -margin
          if (mol.wx < -margin) mol.wx = width + margin
          if (mol.wy > height + margin) mol.wy = -margin
          if (mol.wy < -margin) mol.wy = height + margin
        }
      }

      const sortedInstances = [...instances].sort((a, b) => a.wz - b.wz)
      const fov = 400
      for (const mol of sortedInstances) {
        try {
          drawMolecule(mol, fov)
        } catch (e) {
          // 单个分子绘制错误不影响全局
        }
      }

      animationRef.current = requestAnimationFrame(animate)
    }

    animate()

    const handleResize = () => {
      width = canvas.width = parent.offsetWidth
      height = canvas.height = parent.offsetHeight
      for (const s of stars) {
        s.x = Math.random() * width
        s.y = Math.random() * height
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      canvas.removeEventListener('mousemove', handleMouseMove)
      canvas.removeEventListener('mousedown', handleMouseDown)
      canvas.removeEventListener('mouseup', handleMouseUp)
      canvas.removeEventListener('mouseleave', handleMouseLeave)
      canvas.removeEventListener('touchstart', handleTouchStart)
      canvas.removeEventListener('touchmove', handleTouchMove)
      canvas.removeEventListener('touchend', handleTouchEnd)
      if (animationRef.current) cancelAnimationFrame(animationRef.current)
    }
  }, [])

  const features = [
    { icon: Atom, title: '分子设计', desc: 'AI驱动的分子生成与优化', path: '/molecules' },
    { icon: Zap, title: '活性预测', desc: '深度学习靶点活性评估', path: '/activity' },
    { icon: Shield, title: 'ADMET分析', desc: '药代动力学与毒性预测', path: '/admet' },
    { icon: Sparkles, title: '分子对接', desc: '高精度结合模拟', path: '/docking' },
    { icon: Database, title: '项目管理', desc: '全流程追踪与协作', path: '/projects' },
    { icon: ArrowRight, title: 'Pipeline', desc: '自动化设计管线', path: '/pipeline' },
  ]

  return (
    <div className="relative min-h-screen w-full overflow-hidden bg-[#02040a] -m-6">
      <style>{`
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-up {
          animation: fadeUp 0.6s cubic-bezier(0.22, 1, 0.36, 1) forwards;
          opacity: 0;
        }
      `}</style>
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full"
        style={{ zIndex: 1 }}
      />

      <div className="relative z-10 flex flex-col items-center justify-center min-h-screen px-6 pointer-events-none">
        <div className="text-center max-w-3xl mx-auto">
          <h1 className="text-4xl md:text-6xl font-bold mb-6 tracking-tight leading-tight animate-fade-up" style={{ animationDelay: '0.1s' }}>
            <span className="bg-gradient-to-br from-white via-slate-200 to-slate-400 bg-clip-text text-transparent block">
              AI-Powered
            </span>
            <br />
            <span className="bg-gradient-to-r from-blue-400 via-cyan-300 to-emerald-300 bg-clip-text text-transparent block">
              Molecular Design
            </span>
          </h1>

          <p className="text-base md:text-lg text-slate-400 mb-10 leading-relaxed max-w-2xl mx-auto animate-fade-up" style={{ animationDelay: '0.25s' }}>
            AI 驱动的药物分子设计平台
            <br />
            从分子生成到优化，加速新药发现
          </p>

          <div className="flex items-center justify-center gap-4 animate-fade-up" style={{ animationDelay: '0.4s' }}>
            <Link
              to="/projects"
              className="inline-flex items-center gap-2 px-8 py-3.5 bg-transparent text-white rounded-full font-semibold text-sm border border-white/30 hover:bg-white/10 hover:border-white/50 transition pointer-events-auto"
            >
              开始设计
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              to="/about"
              className="inline-flex items-center gap-2 px-8 py-3.5 bg-transparent text-slate-300 rounded-full font-semibold text-sm border border-white/20 hover:bg-white/5 hover:border-white/30 transition pointer-events-auto"
            >
              了解更多
            </Link>
          </div>
        </div>
      </div>

      <div className="absolute bottom-0 left-0 right-0 h-24 bg-gradient-to-t from-[#02040a] to-transparent pointer-events-none" style={{ zIndex: 5 }} />
    </div>
  )
}

export default HomePage
