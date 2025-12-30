// Background Script - 处理扩展生命周期和消息传递

import type { ChatRequest, ChatResponse } from './types'
import { MESSAGE_ACTIONS } from './constants'
import { Base64 } from './services/base64'

// 监听扩展安装
chrome.runtime.onInstalled.addListener(() => {
  console.log('小红书发布助手扩展已安装')
})

// 监听扩展图标点击，切换侧边栏显示/隐藏
chrome.action.onClicked.addListener(async (tab) => {
  if (!tab.id) return

  // 检查是否是特殊页面（无法注入 content script）
  if (
    tab.url?.startsWith('chrome://') ||
    tab.url?.startsWith('chrome-extension://') ||
    tab.url?.startsWith('edge://')
  ) {
    console.warn('当前页面不支持 content script:', tab.url)
    return
  }

  // 向当前标签页的 content script 发送消息
  try {
    await chrome.tabs.sendMessage(tab.id, { action: MESSAGE_ACTIONS.TOGGLE_SIDEBAR })
    console.log('已发送切换侧边栏消息')
  } catch (error) {
    // 如果发送消息失败，可能是因为 content script 还未加载
    console.warn('发送消息失败，content script 可能未加载:', error)
    console.log('提示：请刷新页面以确保 content script 正确加载')
  }
})

// 处理来自 content script 的 API 请求（用于绕过 CORS）
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.action === MESSAGE_ACTIONS.CHAT_REQUEST) {
    // 异步处理请求
    handleChatRequest(message.data)
      .then((result) => sendResponse({ success: true, data: result }))
      .catch((error) => sendResponse({ success: false, error: error.message }))

    // 返回 true 表示将异步发送响应
    return true
  }
  if (message.action === MESSAGE_ACTIONS.EXPORT_COOKIES) {
    exportCookies()
      .then((result) => sendResponse({ success: true, data: result }))
      .catch((error) => sendResponse({ success: false, error: error.message }))
    return true
  }
})

/**
 * 处理聊天请求（用于发布内容）
 */
async function handleChatRequest(requestData: ChatRequest): Promise<ChatResponse> {
  try {
    const response = await fetch(`${requestData.apiBaseUrl}/api/v1/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: requestData.message,
        thread_id: requestData.thread_id,
        reset: requestData.reset,
      }),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '请求失败' }))
      throw new Error(errorData.detail || errorData.message || `HTTP ${response.status}`)
    }

    const result = await response.json()
    return result
  } catch (error: any) {
    console.error('Background: 聊天请求失败:', error)
    throw error
  }
}

async function exportCookies(): Promise<{ count: number; filename: string }> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  if (!tab || !tab.url) {
    throw new Error('无法获取当前标签页 URL')
  }
  const url = tab.url
  const cookies = await chrome.cookies.getAll({ url })
  const hostname = new URL(url).hostname.replace(/[:\/\\]/g, '_')
  const filename = `cookies_${hostname}_${Date.now()}.txt`
  const data = JSON.stringify(cookies, null, 2)
  const base64 = new Base64()
  const dataUrl = 'data:text/plain;charset=utf-8,' + base64.encode(encodeURIComponent(data))
  await chrome.downloads.download({
    url: dataUrl,
    filename,
    saveAs: true,
    conflictAction: 'uniquify'
  })
  return { count: cookies.length, filename }
}
