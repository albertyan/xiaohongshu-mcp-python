<script setup lang="ts">
import { MESSAGE_ACTIONS } from './constants'

// const toggleSidebar = async () => {
//   const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })

//   if (tab.id) {
//     try {
//       await chrome.tabs.sendMessage(tab.id, { action: MESSAGE_ACTIONS.TOGGLE_SIDEBAR })
//       console.log('已切换侧边栏')
//     } catch (error) {
//       console.error('切换侧边栏失败:', error)
//     }
//   }
// }

const exportCookies = async () => {
  try {
    const result = await chrome.runtime.sendMessage({ action: MESSAGE_ACTIONS.EXPORT_COOKIES })
    if (result?.success) {
      console.log(`已导出 ${result.data.count} 条 Cookies 到 ${result.data.filename}`)
    } else {
      console.error('导出 Cookies 失败:', result?.error)
    }
  } catch (error) {
    console.error('导出 Cookies 失败:', error)
  }
}
</script>

<template>
  <div class="popup">
    <h1>小红书助手</h1>
    <div class="popup-content">
      <!-- <p>点击下方按钮切换侧边栏显示/隐藏</p>
      <button class="btn-toggle" @click="toggleSidebar">
        切换侧边栏
      </button> -->
      <button class="btn-export" @click="exportCookies">
        导出当前站点 Cookies
      </button>
      <div class="info">
        <p>💡 提示：你也可以直接点击扩展图标来切换侧边栏</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.popup {
  width: 320px;
  padding: 20px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

.popup h1 {
  margin: 0 0 16px 0;
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.popup-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.popup-content p {
  margin: 0;
  font-size: 14px;
  color: #666;
  line-height: 1.5;
}

.btn-toggle {
  width: 100%;
  padding: 12px 16px;
  background: #ff2442;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-toggle:hover {
  background: #e01e3a;
}

.btn-export {
  width: 100%;
  padding: 12px 16px;
  background: #4a90e2;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-export:hover {
  background: #3a78bf;
}

.info {
  margin-top: 8px;
  padding: 12px;
  background: #f5f5f5;
  border-radius: 6px;
}

.info p {
  margin: 0;
  font-size: 12px;
  color: #666;
}
</style>
