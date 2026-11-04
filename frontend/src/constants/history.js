// 历史记录的状态常量与徽标样式。
//
// 状态值与后端 backend/database/models.py 的 STATUS_* 一一对应，
// 全前端只此一处定义：改状态语义只需要改这里，列表页与详情页都跟着变。

export const HISTORY_STATUS = {
  PARSED: 'parsed',
  AI_DONE: 'ai_done',
  AI_FAILED: 'ai_failed',
}

// 状态徽标：列表页直接用，样式跟着徽标一起改
export const HISTORY_STATUS_META = {
  [HISTORY_STATUS.PARSED]: { label: '已解析', badge: 'bg-gray-100 text-[#86868b]' },
  [HISTORY_STATUS.AI_DONE]: { label: 'AI 已总结', badge: 'bg-green-50 text-green-600' },
  [HISTORY_STATUS.AI_FAILED]: { label: 'AI 失败', badge: 'bg-orange-50 text-orange-600' },
}
