const app = getApp()
Page({
  data: { events: [] },
  onShow() { this.load() },
  async load() {
    try {
      const [eventsRes, branchesRes] = await Promise.all([
        app.request({ url: '/events/' }),
        app.request({ url: '/branches/' })
      ])
      // 建立 branch id → name 映射
      const branchMap = {}
      ;(branchesRes || []).forEach(b => { branchMap[b.id] = b.name })
      // 计算活动状态
      const now = new Date()
      const events = (eventsRes || []).map(e => {
        const deadline = e.signup_deadline ? new Date(e.signup_deadline) : null
        const eventTime = e.event_time ? new Date(e.event_time) : null
        return {
          ...e,
          _status: !deadline ? 'open' : (now > deadline ? 'closed' : 'open'),
          _ended: eventTime && now > eventTime,
          _branchName: e.branch_id ? (branchMap[e.branch_id] || '支部活动') : '全市活动'
        }
      })
      this.setData({ events })
    } catch (e) {}
  },
  goDetail(e) { wx.navigateTo({ url: `/pages/event/detail?id=${e.currentTarget.dataset.id}` }) }
})
