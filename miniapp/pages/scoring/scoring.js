const app = getApp()
Page({
  data: { board: null, tasks: [] },
  onLoad() { this.load() },
  async load() {
    const mid = app.globalData.memberId || 1
    try {
      const [board, tasks] = await Promise.all([
        app.request({ url: `/scoring/candidate/${mid}` }),
        app.request({ url: `/scoring/candidate/${mid}/tasks` })
      ])
      this.setData({ board, tasks: tasks || [] })
    } catch (e) {}
  },
  goRecords() { wx.navigateTo({ url: '/pages/scoring/detail' }) }
})
