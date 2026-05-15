const app = getApp()
Page({
  data: { board: null, tasks: [], dimensions: [] },
  onLoad() { this.load() },
  async load() {
    const mid = app.globalData.memberId
    if (!mid) {
      wx.showToast({ title: '请先登录', icon: 'none' })
      return
    }
    try {
      const [board, tasks] = await Promise.all([
        app.request({ url: `/scoring/candidate/${mid}` }),
        app.request({ url: `/scoring/candidate/${mid}/tasks` })
      ])
      // 将 dimensions 对象转为数组便于渲染
      const dims = board.dimensions || {}
      const dimensions = Object.keys(dims).map(key => ({
        key,
        label: dims[key].label,
        score: dims[key].score,
        max_score: dims[key].max_score,
        is_reached: dims[key].is_reached
      }))
      this.setData({ board, tasks: tasks || [], dimensions })
    } catch (e) {}
  },
  goRecords() { wx.navigateTo({ url: '/pages/scoring/detail' }) },
  goThought() { wx.navigateTo({ url: '/pages/scoring/thought' }) }
})
